// Example Go file with logging patterns
package main

import (
	"log"
	"os"

	"github.com/rs/zerolog"
)

var logger = zerolog.New(os.Stdout).With().Timestamp().Logger()

func getUser(userID int) error {
	log.Printf("Fetching user with ID: %d", userID)

	if userID < 0 {
		log.Printf("ERROR: Invalid user ID: %d", userID)
		return nil
	}

	log.Printf("User %d retrieved successfully", userID)
	return nil
}

func processData() error {
	logger.Info().Msg("Starting data processing")

	err := doSomething()
	if err != nil {
		logger.Error().Err(err).Msg("Failed to process data")
		return err
	}

	logger.Info().Msg("Data processing completed")
	return nil
}

func doSomething() error {
	return nil
}

func main() {
	log.Println("Application starting")

	err := getUser(123)
	if err != nil {
		log.Fatalf("Fatal error: %v", err)
	}

	processData()

	log.Println("Application finished")
}
