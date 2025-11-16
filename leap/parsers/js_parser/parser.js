#!/usr/bin/env node

const fs = require('fs');
const path = require('path');
const acorn = require('acorn');
const walk = require('acorn-walk');
const { parse: tsParse } = require('@typescript-eslint/typescript-estree');

/**
 * LogEntry represents a single extracted log statement
 */
class LogEntry {
  constructor({ language, filePath, lineNumber, logLevel, logTemplate, codeContext }) {
    this.language = language;
    this.file_path = filePath;
    this.line_number = lineNumber;
    this.log_level = logLevel;
    this.log_template = logTemplate;
    this.code_context = codeContext;
  }
}

/**
 * JSLogParser extracts log statements from JavaScript/TypeScript source code
 */
class JSLogParser {
  constructor(source, filePath, isTypeScript = false) {
    this.source = source;
    this.filePath = filePath;
    this.isTypeScript = isTypeScript;
    this.sourceLines = source.split('\n');
    this.entries = [];
    this.currentFunction = null;
  }

  /**
   * Parse the source code and extract log entries
   */
  parse() {
    try {
      let ast;

      if (this.isTypeScript) {
        // Parse TypeScript
        ast = tsParse(this.source, {
          loc: true,
          range: true,
          ecmaVersion: 'latest',
          sourceType: 'module',
        });
      } else {
        // Parse JavaScript
        ast = acorn.parse(this.source, {
          ecmaVersion: 'latest',
          sourceType: 'module',
          locations: true,
        });
      }

      this.walkAST(ast);
    } catch (error) {
      throw new Error(`Failed to parse ${this.isTypeScript ? 'TypeScript' : 'JavaScript'}: ${error.message}`);
    }

    return this.entries;
  }

  /**
   * Walk the AST and find log calls
   */
  walkAST(ast) {
    // Use custom recursive walk for both JS and TS to avoid acorn-walk compatibility issues
    this.visitNode(ast);
  }

  /**
   * Recursively visit AST nodes
   */
  visitNode(node) {
    if (!node || typeof node !== 'object') {
      return;
    }

    // Handle function declarations/expressions - track current function context
    if (node.type === 'FunctionDeclaration' ||
        node.type === 'FunctionExpression' ||
        node.type === 'ArrowFunctionExpression' ||
        node.type === 'MethodDefinition') {
      const oldFunc = this.currentFunction;
      this.currentFunction = node;
      this.visitChildren(node);
      this.currentFunction = oldFunc;
      return;
    }

    // Handle call expressions - check for log calls
    if (node.type === 'CallExpression') {
      const entry = this.extractLogEntry(node);
      if (entry) {
        this.entries.push(entry);
      }
    }

    // Visit all child nodes
    this.visitChildren(node);
  }

  /**
   * Visit all children of a node
   */
  visitChildren(node) {
    for (const key in node) {
      if (key === 'loc' || key === 'range' || key === 'tokens' || key === 'comments') {
        continue; // Skip metadata
      }

      const child = node[key];

      if (Array.isArray(child)) {
        for (const item of child) {
          this.visitNode(item);
        }
      } else if (child && typeof child === 'object' && child.type) {
        this.visitNode(child);
      }
    }
  }

  /**
   * Extract a log entry from a call expression
   */
  extractLogEntry(node) {
    const { methodName, logLevel } = this.identifyLogCall(node);

    if (!methodName) {
      return null;
    }

    const lineNumber = node.loc?.start.line || 0;
    const logTemplate = this.extractLogTemplate(node);

    if (!logTemplate) {
      return null;
    }

    const codeContext = this.extractContext(node);
    const language = this.isTypeScript ? 'typescript' : 'javascript';

    return new LogEntry({
      language,
      filePath: this.filePath,
      lineNumber,
      logLevel,
      logTemplate,
      codeContext,
    });
  }

  /**
   * Identify if a call is a logging call
   */
  identifyLogCall(node) {
    const callee = node.callee;

    if (callee.type === 'MemberExpression') {
      const objectName = this.getObjectName(callee.object);
      const methodName = callee.property.name;

      // console.log, console.error, etc.
      if (objectName === 'console') {
        const logLevel = this.getConsoleLogLevel(methodName);
        if (logLevel) {
          return { methodName, logLevel };
        }
      }

      // winston, pino, bunyan, log4js, etc.
      if (this.isLoggerObject(objectName) && this.isLogMethod(methodName)) {
        const logLevel = this.getStructuredLogLevel(methodName);
        return { methodName, logLevel };
      }
    }

    return { methodName: null, logLevel: null };
  }

  /**
   * Get the name of an object from a MemberExpression or Identifier
   */
  getObjectName(node) {
    if (node.type === 'Identifier') {
      return node.name;
    }

    if (node.type === 'MemberExpression') {
      // Handle chained calls like this.logger, app.logger
      const prop = node.property.name;
      if (prop === 'logger' || prop === 'log') {
        return prop;
      }
      return this.getObjectName(node.object);
    }

    return null;
  }

  /**
   * Check if object name looks like a logger
   */
  isLoggerObject(name) {
    const loggerNames = ['logger', 'log', 'winston', 'pino', 'bunyan', 'log4js', 'console'];
    return loggerNames.includes(name);
  }

  /**
   * Check if method name is a log method
   */
  isLogMethod(name) {
    const logMethods = ['debug', 'info', 'warn', 'warning', 'error', 'fatal', 'trace', 'log'];
    return logMethods.includes(name);
  }

  /**
   * Get log level for console methods
   */
  getConsoleLogLevel(methodName) {
    const levels = {
      log: 'info',
      debug: 'debug',
      info: 'info',
      warn: 'warn',
      error: 'error',
      trace: 'debug',
    };
    return levels[methodName] || null;
  }

  /**
   * Get log level for structured logging methods
   */
  getStructuredLogLevel(methodName) {
    const levels = {
      debug: 'debug',
      trace: 'debug',
      info: 'info',
      log: 'info',
      warn: 'warn',
      warning: 'warn',
      error: 'error',
      fatal: 'fatal',
    };
    return levels[methodName] || 'info';
  }

  /**
   * Extract log template from call arguments
   */
  extractLogTemplate(node) {
    if (!node.arguments || node.arguments.length === 0) {
      return null;
    }

    const firstArg = node.arguments[0];

    // String literal
    if (firstArg.type === 'Literal' && typeof firstArg.value === 'string') {
      return JSON.stringify(firstArg.value);
    }

    // Template literal
    if (firstArg.type === 'TemplateLiteral') {
      return this.templateLiteralToString(firstArg);
    }

    // Object expression (for structured logging)
    if (firstArg.type === 'ObjectExpression') {
      // For winston/pino style: logger.info({ message: "..." })
      const messageProp = firstArg.properties.find(
        (prop) => prop.key && prop.key.name === 'message'
      );
      if (messageProp && messageProp.value.type === 'Literal') {
        return JSON.stringify(messageProp.value.value);
      }
      return '{...}';
    }

    // Try to extract source text
    if (firstArg.range) {
      const [start, end] = firstArg.range;
      return this.source.substring(start, end);
    }

    return '<expression>';
  }

  /**
   * Convert template literal to string representation
   */
  templateLiteralToString(node) {
    let result = '`';

    for (let i = 0; i < node.quasis.length; i++) {
      result += node.quasis[i].value.raw;

      if (i < node.expressions.length) {
        result += '${...}';
      }
    }

    result += '`';
    return result;
  }

  /**
   * Extract code context around the log call
   */
  extractContext(node) {
    if (this.currentFunction && this.currentFunction.loc) {
      const startLine = Math.max(0, this.currentFunction.loc.start.line - 1);
      const endLine = Math.min(this.sourceLines.length, this.currentFunction.loc.end.line);
      return this.sourceLines.slice(startLine, endLine).join('\n');
    }

    // Fallback: extract a window around the log call
    const lineNumber = node.loc?.start.line || 1;
    const startLine = Math.max(0, lineNumber - 6);
    const endLine = Math.min(this.sourceLines.length, lineNumber + 2);

    return this.sourceLines.slice(startLine, endLine).join('\n');
  }
}

/**
 * Main execution
 */
async function main() {
  if (process.argv.length < 3) {
    console.error(`Usage: ${process.argv[1]} <js/ts-file>`);
    process.exit(1);
  }

  const filePath = process.argv[2];

  if (!fs.existsSync(filePath)) {
    console.error(`File not found: ${filePath}`);
    process.exit(1);
  }

  try {
    const source = fs.readFileSync(filePath, 'utf-8');
    const ext = path.extname(filePath).toLowerCase();
    const isTypeScript = ext === '.ts' || ext === '.tsx';

    const parser = new JSLogParser(source, filePath, isTypeScript);
    const entries = parser.parse();

    // Output as JSON
    console.log(JSON.stringify(entries, null, 2));
  } catch (error) {
    console.error(`Error parsing file: ${error.message}`);
    console.error(error.stack);
    process.exit(1);
  }
}

main();
