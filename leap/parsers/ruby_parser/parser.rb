#!/usr/bin/env ruby
# frozen_string_literal: true

require 'json'

# LogEntry represents a single extracted log statement
class LogEntry
  attr_reader :language, :file_path, :line_number, :log_level, :log_template, :code_context

  def initialize(language:, file_path:, line_number:, log_level:, log_template:, code_context:)
    @language = language
    @file_path = file_path
    @line_number = line_number
    @log_level = log_level
    @log_template = log_template
    @code_context = code_context
  end

  def to_h
    {
      language: @language,
      file_path: @file_path,
      line_number: @line_number,
      log_level: @log_level,
      log_template: @log_template,
      code_context: @code_context
    }
  end
end

# RubyLogParser extracts log statements from Ruby source code
class RubyLogParser
  # Standard logger method names and their levels
  LOG_METHODS = {
    'debug' => 'debug',
    'info' => 'info',
    'warn' => 'warn',
    'warning' => 'warn',
    'error' => 'error',
    'fatal' => 'fatal',
    'unknown' => 'error'
  }.freeze

  # Regex pattern to match logger calls
  # Matches: logger.info(...), @logger.error(...), Rails.logger.warn(...)
  LOG_PATTERN = /(?:@?[a-z_]\w*\.)*logger\.(debug|info|warn|warning|error|fatal|unknown)\s*[(\s"']/

  def initialize(source, file_path)
    @source = source
    @file_path = file_path
    @source_lines = source.lines
    @entries = []
  end

  def parse
    @source_lines.each_with_index do |line, index|
      line_number = index + 1

      # Check if line matches logger pattern
      if line =~ LOG_PATTERN
        method_name = $1
        log_level = LOG_METHODS[method_name]
        next unless log_level

        # Extract the full message
        log_template = extract_message(line)

        # Extract context (a few lines around the log call)
        code_context = extract_context(line_number)

        entry = LogEntry.new(
          language: 'ruby',
          file_path: @file_path,
          line_number: line_number,
          log_level: log_level,
          log_template: log_template,
          code_context: code_context
        )

        @entries << entry
      end
    end

    @entries
  end

  private

  def extract_message(line)
    # Try to extract the message after the method call
    # Look for string literals with quotes or parentheses
    if line =~ /\.(?:debug|info|warn|warning|error|fatal|unknown)\s*[\("'](.+?)[\)"']/
      return "\"#{$1}\""
    elsif line =~ /\.(?:debug|info|warn|warning|error|fatal|unknown)\s+["'](.+?)["']/
      return "\"#{$1}\""
    elsif line =~ /\.(?:debug|info|warn|warning|error|fatal|unknown)\s+(.+?)$/
      return "\"#{$1.strip}\""
    end

    # Fallback
    '"<message>"'
  end

  def extract_context(line_number)
    # Extract a window of lines around the log call
    start_line = [0, line_number - 6].max
    end_line = [line_number + 2, @source_lines.length].min

    @source_lines[start_line...end_line].join
  end
end

# Main execution
if ARGV.length < 1
  warn "Usage: #{$PROGRAM_NAME} <ruby-file>"
  exit 1
end

file_path = ARGV[0]

unless File.exist?(file_path)
  warn "File not found: #{file_path}"
  exit 1
end

begin
  source = File.read(file_path)

  parser = RubyLogParser.new(source, file_path)
  entries = parser.parse

  # Output as JSON
  output = entries.map(&:to_h)
  puts JSON.pretty_generate(output)
rescue => e
  warn "Error parsing file: #{e.message}"
  warn e.backtrace.join("\n")
  exit 1
end
