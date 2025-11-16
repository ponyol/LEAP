# Example Ruby file with logging patterns
require 'logger'

class UserService
  def initialize
    @logger = Logger.new(STDOUT)
  end

  def get_user(user_id)
    @logger.info "Fetching user with ID: #{user_id}"

    if user_id < 0
      @logger.error "Invalid user ID: #{user_id}"
      return nil
    end

    if user_id == 404
      @logger.warn "User not found in database"
      return nil
    end

    @logger.debug "Successfully retrieved user #{user_id}"
    { id: user_id, name: 'John Doe' }
  end

  def create_user(username, email)
    @logger.info "Creating new user: #{username}"

    if email.nil? || email.empty?
      @logger.error "Email is required"
      raise ArgumentError, "Email is required"
    end

    user = { username: username, email: email }
    @logger.debug "User created successfully: #{user}"

    user
  end
end

# Rails-style logging
Rails.logger.info "Application starting" if defined?(Rails)
