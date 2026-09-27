package com.cardiosaarthi.review.queue;

import java.util.List;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/queue")
public class QueueController {

    /** Enough to fill a screen; a reviewer does not page through hundreds. */
    private static final int DEFAULT_LIMIT = 25;
    private static final int MAX_LIMIT = 200;

    private final QueueRepository queue;

    QueueController(QueueRepository queue) {
        this.queue = queue;
    }

    /**
     * @param items pending cases for this page
     * @param total pending cases matching the filters, ignoring paging
     */
    public record QueuePage(List<QueueEntry> items, int total, int limit, int offset, QueueOrder order) {
    }

    @GetMapping
    public QueuePage queue(
            @RequestParam(defaultValue = "BANK_FIRST") QueueOrder order,
            @RequestParam(required = false) String condition,
            @RequestParam(required = false) String status,
            @RequestParam(defaultValue = "" + DEFAULT_LIMIT) int limit,
            @RequestParam(defaultValue = "0") int offset) {

        int boundedLimit = Math.clamp(limit, 1, MAX_LIMIT);
        int boundedOffset = Math.max(offset, 0);

        return new QueuePage(
                queue.page(order, condition, status, boundedLimit, boundedOffset),
                queue.count(condition, status),
                boundedLimit,
                boundedOffset,
                order);
    }

    /**
     * The next case to review, as a single object rather than a list.
     *
     * <p>The review console's main loop is "give me the next one", and having the
     * server decide what next means keeps that policy in one place instead of in
     * every client that asks.
     */
    @GetMapping("/next")
    public QueueEntry next(
            @RequestParam(defaultValue = "BANK_FIRST") QueueOrder order,
            @RequestParam(required = false) String condition) {
        List<QueueEntry> head = queue.page(order, condition, null, 1, 0);
        return head.isEmpty() ? null : head.getFirst();
    }
}
