package com.cardiosaarthi.review.config;

import java.util.List;

import javax.crypto.spec.SecretKeySpec;

import com.nimbusds.jose.jwk.source.ImmutableSecret;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.HttpMethod;
import org.springframework.security.config.Customizer;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.http.SessionCreationPolicy;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.security.oauth2.jose.jws.MacAlgorithm;
import org.springframework.security.oauth2.jwt.JwtDecoder;
import org.springframework.security.oauth2.jwt.JwtEncoder;
import org.springframework.security.oauth2.jwt.NimbusJwtDecoder;
import org.springframework.security.oauth2.jwt.NimbusJwtEncoder;
import org.springframework.security.oauth2.server.resource.authentication.JwtAuthenticationConverter;
import org.springframework.security.oauth2.server.resource.authentication.JwtGrantedAuthoritiesConverter;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.web.cors.CorsConfiguration;
import org.springframework.web.cors.CorsConfigurationSource;
import org.springframework.web.cors.UrlBasedCorsConfigurationSource;

/**
 * Authentication for the review service.
 *
 * <p>Two mechanisms, deliberately:
 *
 * <ul>
 *   <li><b>Bearer tokens</b> for the React console. It posts credentials once to
 *       {@code /api/auth/login/{role}} and carries a signed token afterwards.
 *   <li><b>HTTP Basic</b> for scripts, tests and curl. Removing it would mean
 *       every diagnostic command had to obtain a token first, for no security
 *       gain on a service that is behind TLS either way.
 * </ul>
 *
 * <p>The token carries identity only. What someone may do is read from the
 * database on each request, so withdrawing access takes effect at once rather
 * than whenever an unexpired token runs out.
 *
 * <p>Anywhere that is not localhost this service must be behind TLS. A bearer
 * token in a header and Basic credentials in base64 are both readable in
 * transit.
 */
@Configuration
public class SecurityConfig {

    @Bean
    SecurityFilterChain filterChain(HttpSecurity http, JwtAuthenticationConverter jwtConverter) throws Exception {
        return http
                // Resolved by bean name. Injecting CorsConfigurationSource by
                // type is ambiguous: HandlerMappingIntrospector implements it too.
                .cors(Customizer.withDefaults())
                // No session and no browser form posts, so there is no CSRF
                // vector for a token to protect. Revisit if a cookie appears.
                .csrf(csrf -> csrf.disable())
                .sessionManagement(s -> s.sessionCreationPolicy(SessionCreationPolicy.STATELESS))
                .authorizeHttpRequests(auth -> auth
                        .requestMatchers(HttpMethod.OPTIONS, "/**").permitAll()
                        .requestMatchers("/actuator/health", "/actuator/health/**", "/actuator/info").permitAll()
                        // The one endpoint that cannot require a credential,
                        // being where credentials are exchanged for a token.
                        .requestMatchers(HttpMethod.POST, "/api/auth/login/**").permitAll()
                        // Everything else, the waveform images included. These
                        // are real patient recordings: de-identified, but not
                        // ours to leave open.
                        .requestMatchers("/api/**").authenticated()
                        .anyRequest().denyAll())
                .httpBasic(Customizer.withDefaults())
                .oauth2ResourceServer(oauth2 -> oauth2.jwt(jwt -> jwt.jwtAuthenticationConverter(jwtConverter)))
                .build();
    }

    /**
     * Turns the token's {@code role} claim into a Spring authority, so
     * {@code hasRole('FACULTY')} works the same whether the request arrived with
     * a token or with Basic credentials.
     */
    @Bean
    JwtAuthenticationConverter jwtAuthenticationConverter() {
        JwtGrantedAuthoritiesConverter authorities = new JwtGrantedAuthoritiesConverter();
        authorities.setAuthorityPrefix("ROLE_");
        authorities.setAuthoritiesClaimName("role");

        JwtAuthenticationConverter converter = new JwtAuthenticationConverter();
        converter.setJwtGrantedAuthoritiesConverter(authorities);
        return converter;
    }

    @Bean
    JwtEncoder jwtEncoder(ApiProperties properties) {
        return new NimbusJwtEncoder(new ImmutableSecret<>(secretKey(properties)));
    }

    @Bean
    JwtDecoder jwtDecoder(ApiProperties properties) {
        return NimbusJwtDecoder.withSecretKey(secretKey(properties))
                .macAlgorithm(MacAlgorithm.HS256)
                .build();
    }

    private static SecretKeySpec secretKey(ApiProperties properties) {
        String secret = properties.jwtSecret();
        if (secret == null || secret.length() < 32) {
            // HS256 with a short key is not a small weakness, it is a guessable
            // signature. Failing at start-up is the only safe response.
            throw new IllegalStateException(
                    "cardiosaarthi.jwt-secret must be at least 32 characters. "
                            + "Set CARDIO_JWT_SECRET in .env.");
        }
        return new SecretKeySpec(secret.getBytes(), "HmacSHA256");
    }

    @Bean
    PasswordEncoder passwordEncoder() {
        return new BCryptPasswordEncoder();
    }

    @Bean
    CorsConfigurationSource corsConfigurationSource(ApiProperties properties) {
        CorsConfiguration config = new CorsConfiguration();
        config.setAllowedOrigins(properties.corsAllowedOrigins());
        config.setAllowedMethods(List.of("GET", "POST", "OPTIONS"));
        config.setAllowedHeaders(List.of("Authorization", "Content-Type"));
        config.setAllowCredentials(true);
        UrlBasedCorsConfigurationSource source = new UrlBasedCorsConfigurationSource();
        source.registerCorsConfiguration("/api/**", config);
        return source;
    }
}
