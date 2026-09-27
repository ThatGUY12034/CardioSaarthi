package com.cardiosaarthi.review.reviewer;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api")
public class ReviewerController {

    private final ReviewerService reviewers;

    ReviewerController(ReviewerService reviewers) {
        this.reviewers = reviewers;
    }

    /** Who the caller is, according to the server. */
    @GetMapping("/me")
    public Reviewer me() {
        return reviewers.current();
    }
}
