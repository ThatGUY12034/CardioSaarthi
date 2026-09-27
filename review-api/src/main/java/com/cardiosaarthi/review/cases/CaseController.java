package com.cardiosaarthi.review.cases;

import java.io.IOException;
import java.io.InputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Duration;

import org.springframework.core.io.InputStreamResource;
import org.springframework.http.CacheControl;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import com.cardiosaarthi.review.config.ApiProperties;
import com.cardiosaarthi.review.error.NotFoundException;

@RestController
@RequestMapping("/api/cases")
public class CaseController {

    private final CaseRepository cases;
    private final ApiProperties properties;

    CaseController(CaseRepository cases, ApiProperties properties) {
        this.cases = cases;
        this.properties = properties;
    }

    @GetMapping("/{id}")
    public CaseDetail detail(@PathVariable long id) {
        return cases.findDetail(id)
                .orElseThrow(() -> new NotFoundException("no case with id " + id));
    }

    /**
     * The rendered ECG, clean or annotated.
     *
     * <p>Served through the API rather than as a static directory so that the
     * authentication rules apply to the waveform images too. These are real
     * patient recordings; de-identified, but not ours to leave open.
     */
    @GetMapping("/{id}/image/{kind}")
    public ResponseEntity<InputStreamResource> image(@PathVariable long id, @PathVariable String kind)
            throws IOException {

        String stored = cases.findImagePath(id, kind)
                .orElseThrow(() -> new NotFoundException("no %s image for case %d".formatted(kind, id)));

        Path root = properties.resolvedRoot();
        Path file = root.resolve(stored).normalize();

        // The path comes from our own ingest, but a stored value is still data,
        // and a check that costs nothing removes the whole class of problem.
        if (!file.startsWith(root)) {
            throw new NotFoundException("image path for case %d resolves outside the repository".formatted(id));
        }
        if (!Files.isRegularFile(file)) {
            throw new NotFoundException(
                    "case %d records a %s image but %s is not on disk".formatted(id, kind, stored));
        }

        InputStream stream = Files.newInputStream(file);
        return ResponseEntity.ok()
                .contentType(MediaType.IMAGE_PNG)
                .contentLength(Files.size(file))
                // A rendered ECG never changes: the pipeline writes a new file
                // for a new measurement rather than editing one in place.
                .cacheControl(CacheControl.maxAge(Duration.ofDays(30)).cachePrivate())
                .header(HttpHeaders.CONTENT_DISPOSITION, "inline; filename=\"%d_%s.png\"".formatted(id, kind))
                .body(new InputStreamResource(stream));
    }
}
