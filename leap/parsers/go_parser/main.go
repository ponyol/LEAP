package main

import (
	"encoding/json"
	"fmt"
	"go/ast"
	"go/parser"
	"go/token"
	"os"
	"strings"
)

// LogEntry represents a single extracted log statement
type LogEntry struct {
	Language    string  `json:"language"`
	FilePath    string  `json:"file_path"`
	LineNumber  int     `json:"line_number"`
	LogLevel    *string `json:"log_level"`
	LogTemplate string  `json:"log_template"`
	CodeContext string  `json:"code_context"`
}

// Visitor implements ast.Visitor for finding log calls
type Visitor struct {
	fset        *token.FileSet
	filePath    string
	sourceLines []string
	entries     []LogEntry
	currentFunc *ast.FuncDecl
}

func main() {
	if len(os.Args) < 2 {
		fmt.Fprintf(os.Stderr, "Usage: %s <go-file>\n", os.Args[0])
		os.Exit(1)
	}

	filePath := os.Args[1]

	// Parse the Go file
	entries, err := parseGoFile(filePath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error parsing file: %v\n", err)
		os.Exit(1)
	}

	// Output as JSON
	output, err := json.MarshalIndent(entries, "", "  ")
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error marshaling JSON: %v\n", err)
		os.Exit(1)
	}

	fmt.Println(string(output))
}

func parseGoFile(filePath string) ([]LogEntry, error) {
	// Read source file
	sourceBytes, err := os.ReadFile(filePath)
	if err != nil {
		return nil, fmt.Errorf("failed to read file: %w", err)
	}

	source := string(sourceBytes)
	sourceLines := strings.Split(source, "\n")

	// Parse Go source
	fset := token.NewFileSet()
	node, err := parser.ParseFile(fset, filePath, source, parser.ParseComments)
	if err != nil {
		return nil, fmt.Errorf("failed to parse Go source: %w", err)
	}

	// Create visitor and walk AST
	v := &Visitor{
		fset:        fset,
		filePath:    filePath,
		sourceLines: sourceLines,
		entries:     []LogEntry{},
	}

	ast.Walk(v, node)

	return v.entries, nil
}

// Visit implements ast.Visitor
func (v *Visitor) Visit(node ast.Node) ast.Visitor {
	if node == nil {
		return nil
	}

	// Track current function for context
	if funcDecl, ok := node.(*ast.FuncDecl); ok {
		oldFunc := v.currentFunc
		v.currentFunc = funcDecl
		ast.Walk(v, funcDecl.Body)
		v.currentFunc = oldFunc
		return nil
	}

	// Check for function calls
	if callExpr, ok := node.(*ast.CallExpr); ok {
		if entry := v.extractLogEntry(callExpr); entry != nil {
			v.entries = append(v.entries, *entry)
		}
	}

	return v
}

// extractLogEntry extracts a log entry from a call expression
func (v *Visitor) extractLogEntry(call *ast.CallExpr) *LogEntry {
	// Get the function being called
	funcName, logLevel := v.identifyLogCall(call.Fun)
	if funcName == "" {
		return nil
	}

	// Get line number
	pos := v.fset.Position(call.Pos())
	lineNumber := pos.Line

	// Extract log template
	logTemplate := v.extractLogTemplate(call)
	if logTemplate == "" {
		return nil
	}

	// Extract code context
	codeContext := v.extractContext(call)

	return &LogEntry{
		Language:    "go",
		FilePath:    v.filePath,
		LineNumber:  lineNumber,
		LogLevel:    logLevel,
		LogTemplate: logTemplate,
		CodeContext: codeContext,
	}
}

// identifyLogCall checks if a function call is a logging call
func (v *Visitor) identifyLogCall(fun ast.Expr) (string, *string) {
	switch expr := fun.(type) {
	case *ast.SelectorExpr:
		// Handle calls like log.Print(), logger.Info()
		methodName := expr.Sel.Name

		// Standard log package
		if isStdLogMethod(methodName) {
			level := getStdLogLevel(methodName)
			return methodName, &level
		}

		// Check for zerolog/logrus style: logger.Info(), logger.Error()
		if isStructuredLogMethod(methodName) {
			level := getStructuredLogLevel(methodName)
			return methodName, &level
		}

	case *ast.CallExpr:
		// Handle chained calls like logger.Error().Msg("...")
		if sel, ok := expr.Fun.(*ast.SelectorExpr); ok {
			methodName := sel.Sel.Name
			if methodName == "Msg" || methodName == "Msgf" {
				// This is the final .Msg() call in a chain
				// Try to determine level from the chain
				level := v.extractLevelFromChain(expr)
				return methodName, level
			}
		}
	}

	return "", nil
}

// isStdLogMethod checks if a method is from the standard log package
func isStdLogMethod(name string) bool {
	stdMethods := map[string]bool{
		"Print": true, "Printf": true, "Println": true,
		"Fatal": true, "Fatalf": true, "Fatalln": true,
		"Panic": true, "Panicf": true, "Panicln": true,
	}
	return stdMethods[name]
}

// getStdLogLevel returns the log level for standard log methods
func getStdLogLevel(name string) string {
	if strings.HasPrefix(name, "Fatal") {
		return "fatal"
	}
	if strings.HasPrefix(name, "Panic") {
		return "fatal"
	}
	return "info"
}

// isStructuredLogMethod checks if a method is from structured logging libs
func isStructuredLogMethod(name string) bool {
	methods := map[string]bool{
		"Debug": true, "Info": true, "Warn": true, "Warning": true,
		"Error": true, "Fatal": true, "Panic": true,
		"Trace": true, // Some loggers have Trace level
	}
	return methods[name]
}

// getStructuredLogLevel returns the log level for structured logging methods
func getStructuredLogLevel(name string) string {
	switch strings.ToLower(name) {
	case "debug":
		return "debug"
	case "info":
		return "info"
	case "warn", "warning":
		return "warn"
	case "error":
		return "error"
	case "fatal", "panic":
		return "fatal"
	case "trace":
		return "debug"
	default:
		return "info"
	}
}

// extractLevelFromChain extracts log level from a chained call
func (v *Visitor) extractLevelFromChain(call *ast.CallExpr) *string {
	// Walk back through the chain to find the level method
	if sel, ok := call.Fun.(*ast.SelectorExpr); ok {
		if chainCall, ok := sel.X.(*ast.CallExpr); ok {
			if chainSel, ok := chainCall.Fun.(*ast.SelectorExpr); ok {
				methodName := chainSel.Sel.Name
				if isStructuredLogMethod(methodName) {
					level := getStructuredLogLevel(methodName)
					return &level
				}
			}
		}
	}
	return nil
}

// extractLogTemplate extracts the log message template from call arguments
func (v *Visitor) extractLogTemplate(call *ast.CallExpr) string {
	if len(call.Args) == 0 {
		return ""
	}

	// Get the first argument (usually the message)
	firstArg := call.Args[0]

	// Handle string literals
	if lit, ok := firstArg.(*ast.BasicLit); ok && lit.Kind == token.STRING {
		return lit.Value
	}

	// Handle more complex expressions by converting to string
	pos := v.fset.Position(firstArg.Pos())
	end := v.fset.Position(firstArg.End())

	if pos.Line == end.Line && pos.Line > 0 && pos.Line <= len(v.sourceLines) {
		line := v.sourceLines[pos.Line-1]
		if pos.Column > 0 && end.Column > pos.Column && end.Column <= len(line)+1 {
			return line[pos.Column-1 : end.Column-1]
		}
	}

	return fmt.Sprintf("<expression at line %d>", pos.Line)
}

// extractContext extracts surrounding code context
func (v *Visitor) extractContext(call *ast.CallExpr) string {
	if v.currentFunc != nil {
		// Extract the entire function as context
		startPos := v.fset.Position(v.currentFunc.Pos())
		endPos := v.fset.Position(v.currentFunc.End())

		if startPos.Line > 0 && endPos.Line <= len(v.sourceLines) {
			contextLines := v.sourceLines[startPos.Line-1 : endPos.Line]
			return strings.Join(contextLines, "\n")
		}
	}

	// Fallback: return a few lines around the call
	pos := v.fset.Position(call.Pos())
	startLine := max(0, pos.Line-6)
	endLine := min(len(v.sourceLines), pos.Line+2)

	if startLine < endLine {
		contextLines := v.sourceLines[startLine:endLine]
		return strings.Join(contextLines, "\n")
	}

	return ""
}

func max(a, b int) int {
	if a > b {
		return a
	}
	return b
}

func min(a, b int) int {
	if a < b {
		return a
	}
	return b
}
