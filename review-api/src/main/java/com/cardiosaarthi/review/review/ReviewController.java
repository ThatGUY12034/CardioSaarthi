package com.cardiosaarthi.review.review;

import java.util.List;
import java.util.Map;

import jakarta.validation.Valid;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import com.cardiosaarthi.review.reviewer.ReviewerService;

@RestController
@RequestMapping("/api")
public class ReviewController {

    private final ReviewService reviews;
    private final ReviewerService reviewers;

    ReviewController(ReviewService reviews, ReviewerService reviewers) {
        this.reviews = reviews;
        this.reviewers = reviewers;
    }

    /**
     * Record a decision on one case.
     *
     * <p>Returns 404 if the case does not exist, 409 if it was already decided,
     * and 422 if the decision is impossible -- a correction to a measure the case
     * does not have, a value no heart could produce, a rejection with no reason.
     */
    @PostMapping("/cases/{id}/review")
    public ReviewOutcome review(@PathVariable long id, @Valid @RequestBody ReviewRequest request) {
        return reviews.submit(id, request, reviewers.current());
    }

    /**
     * The vocabulary the console needs to build its own form, so the two cannot
     * drift out of step over what a valid rejection reason is.
     */
    @GetMapping("/review/options")
    public Map<String, List<String>> options() {
        return Map.of(
                "actions", List.of(ReviewAction.values()).stream().map(Enum::name).toList(),
                "rejectionReasons", List.of(RejectionReason.values()).stream().map(Enum::name).toList());
    }
}
