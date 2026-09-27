package com.cardiosaarthi.review;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.context.properties.ConfigurationPropertiesScan;

/**
 * The faculty review service.
 *
 * <p>Stands between the measured case bank and the people who decide whether a
 * case is fit to teach with. Its whole job is to make a reviewer's judgement
 * durable and attributable: nothing reaches a student that a named person has not
 * approved, and nothing a reviewer corrects is ever written over the engine's
 * original number.
 */
@SpringBootApplication
@ConfigurationPropertiesScan
public class ReviewApiApplication {

    public static void main(String[] args) {
        SpringApplication.run(ReviewApiApplication.class, args);
    }
}
