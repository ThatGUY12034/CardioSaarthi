package com.cardiosaarthi.review.bank;

import java.util.List;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api")
public class BankController {

    private final BankRepository bank;

    BankController(BankRepository bank) {
        this.bank = bank;
    }

    /** Every syllabus condition and how full its bank is, gaps included. */
    @GetMapping("/conditions")
    public List<ConditionBankEntry> conditions() {
        return bank.conditions();
    }

    /**
     * Pipeline accuracy, measurement agreement and reviewer throughput.
     *
     * <p>Empty until the first review is submitted, which is the honest state:
     * none of these figures can be reported before a reviewer has looked at
     * anything.
     */
    @GetMapping("/stats")
    public Statistics stats() {
        return bank.statistics();
    }
}
