// Example JavaScript file with logging patterns
const winston = require('winston');

const logger = winston.createLogger({
  level: 'info',
  format: winston.format.json(),
  transports: [new winston.transports.Console()],
});

class UserService {
  constructor() {
    this.logger = logger;
  }

  getUser(userId) {
    this.logger.info(`Fetching user with ID: ${userId}`);

    if (userId < 0) {
      this.logger.error(`Invalid user ID: ${userId}`);
      return null;
    }

    if (userId === 404) {
      this.logger.warn('User not found in database');
      return null;
    }

    this.logger.debug(`Successfully retrieved user ${userId}`);
    return { id: userId, name: 'John Doe' };
  }

  createUser(username, email) {
    this.logger.info(`Creating new user: ${username}`);

    if (!email) {
      this.logger.error('Email is required');
      throw new Error('Email is required');
    }

    const user = { username, email };
    this.logger.debug(`User created successfully: ${JSON.stringify(user)}`);

    return user;
  }
}

// Console logging
console.log('Application starting');
console.error('This is an error message');
console.warn('This is a warning message');

module.exports = UserService;
