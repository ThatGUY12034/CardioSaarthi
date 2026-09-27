package com.cardiosaarthi.review;

import java.net.InetSocketAddress;
import java.net.Socket;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.condition.EnabledIf;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc;
import org.springframework.http.MediaType;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.transaction.annotation.Transactional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/**
 * The login flow the React console actually performs.
 *
 * <p>Written against the shape the console already codes against rather than one
 * of my choosing: it posts to {@code /api/auth/login/{role}}, stores
 * {@code data.token} and {@code data.user}, and its axios interceptor clears
 * that token on 401 specifically.
 *
 * <p>That last detail is why several of these assert a status rather than a body.
 * Before they existed every failure answered 500, so a wrong password would have
 * left the login screen reporting a server fault instead of asking the person to
 * check their details.
 */
@SpringBootTest
@AutoConfigureMockMvc
@Transactional
@EnabledIf("databaseIsRunning")
class AuthIntegrationTests {

    private static final String FACULTY_EMAIL = "auth.faculty@example.invalid";
    private static final String STUDENT_EMAIL = "auth.student@example.invalid";
    private static final String COLLEGE_ID = "TE18/2023/C9999";
    private static final String PASSWORD = "correct-horse-battery";

    @Autowired
    private MockMvc mvc;

    @Autowired
    private JdbcClient db;

    @Autowired
    private PasswordEncoder passwordEncoder;

    static boolean databaseIsRunning() {
        try (Socket socket = new Socket()) {
            socket.connect(new InetSocketAddress("127.0.0.1", 55432), 500);
            return true;
        } catch (Exception exception) {
            return false;
        }
    }

    @BeforeEach
    void createAccounts() {
        String hash = passwordEncoder.encode(PASSWORD);
        db.sql("""
                INSERT INTO reviewers (email, full_name, role, password_hash, college_id)
                VALUES (:email, 'Auth Faculty', 'faculty', :hash, :collegeId)
                ON CONFLICT (lower(email)) DO UPDATE SET password_hash = excluded.password_hash,
                                                         college_id = excluded.college_id
                """)
                .param("email", FACULTY_EMAIL)
                .param("hash", hash)
                .param("collegeId", COLLEGE_ID)
                .update();
        db.sql("""
                INSERT INTO students (email, full_name, password_hash)
                VALUES (:email, 'Auth Student', :hash)
                ON CONFLICT (lower(email)) DO UPDATE SET password_hash = excluded.password_hash
                """)
                .param("email", STUDENT_EMAIL)
                .param("hash", hash)
                .update();
    }

    private String login(String role, String payload) throws Exception {
        return mvc.perform(post("/api/auth/login/" + role)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(payload))
                .andReturn().getResponse().getContentAsString();
    }

    private static String field(String json, String name) {
        return json.replaceAll(".*\"" + name + "\"\\s*:\\s*\"([^\"]*)\".*", "$1");
    }

    // -----------------------------------------------------------------------
    // the happy path, in the console's exact shape
    // -----------------------------------------------------------------------
    @Test
    @DisplayName("faculty login returns a token and the user object the console stores")
    void facultyLoginReturnsTokenAndUser() throws Exception {
        mvc.perform(post("/api/auth/login/faculty")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"email\":\"" + FACULTY_EMAIL + "\",\"password\":\"" + PASSWORD
                                + "\",\"mode\":\"email\"}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.token").isNotEmpty())
                .andExpect(jsonPath("$.expiresAt").isNotEmpty())
                .andExpect(jsonPath("$.user.id").isNumber())
                .andExpect(jsonPath("$.user.name").value("Auth Faculty"))
                .andExpect(jsonPath("$.user.role").value("FACULTY"))
                .andExpect(jsonPath("$.user.collegeId").value(COLLEGE_ID));
    }

    @Test
    @DisplayName("no password hash appears anywhere in the response")
    void responseCarriesNoHash() throws Exception {
        String response = login("faculty",
                "{\"email\":\"" + FACULTY_EMAIL + "\",\"password\":\"" + PASSWORD + "\",\"mode\":\"email\"}");

        assertThat(response).doesNotContain("$2a$").doesNotContain("passwordHash");
        String token = field(response, "token");
        assertThat(token.chars().filter(character -> character == '.').count())
                .as("a JWT has three dot-separated segments")
                .isEqualTo(2);
    }

    @Test
    @DisplayName("login by college ID works, because the form offers it")
    void collegeIdLoginWorks() throws Exception {
        mvc.perform(post("/api/auth/login/faculty")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"collegeId\":\"" + COLLEGE_ID + "\",\"password\":\"" + PASSWORD
                                + "\",\"mode\":\"college\"}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.user.role").value("FACULTY"));
    }

    @Test
    @DisplayName("a student signs in against the students table")
    void studentLoginWorks() throws Exception {
        mvc.perform(post("/api/auth/login/student")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"email\":\"" + STUDENT_EMAIL + "\",\"password\":\"" + PASSWORD
                                + "\",\"mode\":\"email\"}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.user.role").value("STUDENT"));
    }

    @Test
    @DisplayName("an issued token opens a protected endpoint")
    void issuedTokenAuthenticatesRequests() throws Exception {
        String response = login("faculty",
                "{\"email\":\"" + FACULTY_EMAIL + "\",\"password\":\"" + PASSWORD + "\",\"mode\":\"email\"}");

        mvc.perform(get("/api/me").header("Authorization", "Bearer " + field(response, "token")))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.email").value(FACULTY_EMAIL));
    }

    // -----------------------------------------------------------------------
    // failures, each with the status the console expects
    // -----------------------------------------------------------------------
    @Test
    @DisplayName("a wrong password is 401, not 500")
    void wrongPasswordIsUnauthorized() throws Exception {
        mvc.perform(post("/api/auth/login/faculty")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"email\":\"" + FACULTY_EMAIL + "\",\"password\":\"wrong\",\"mode\":\"email\"}"))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.message").value("Check your details and try again."));
    }

    @Test
    @DisplayName("an unknown account fails identically to a wrong password")
    void unknownAccountIsIndistinguishable() throws Exception {
        // Telling the two apart tells an attacker which half to keep working on,
        // and tells a legitimate user nothing they can act on.
        String wrongPassword = login("faculty",
                "{\"email\":\"" + FACULTY_EMAIL + "\",\"password\":\"wrong\",\"mode\":\"email\"}");
        String unknownAccount = login("faculty",
                "{\"email\":\"nobody@example.invalid\",\"password\":\"wrong\",\"mode\":\"email\"}");

        assertThat(field(unknownAccount, "message")).isEqualTo(field(wrongPassword, "message"));
    }

    @Test
    @DisplayName("faculty credentials cannot be used through the student form")
    void roleIsCheckedAgainstTheStoredRole() throws Exception {
        mvc.perform(post("/api/auth/login/student")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"email\":\"" + FACULTY_EMAIL + "\",\"password\":\"" + PASSWORD
                                + "\",\"mode\":\"email\"}"))
                .andExpect(status().isUnauthorized());
    }

    @Test
    @DisplayName("an account with no password hash cannot be signed in to")
    void nullHashCannotAuthenticate() throws Exception {
        // The system account that seeds development fixtures is exactly this.
        db.sql("""
                INSERT INTO reviewers (email, full_name, role, password_hash)
                VALUES ('auth.nohash@example.invalid', 'No Hash', 'faculty', NULL)
                ON CONFLICT (lower(email)) DO UPDATE SET password_hash = NULL
                """).update();

        mvc.perform(post("/api/auth/login/faculty")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"email\":\"auth.nohash@example.invalid\",\"password\":\"x\",\"mode\":\"email\"}"))
                .andExpect(status().isUnauthorized());
    }

    @Test
    @DisplayName("an unbuilt role says so rather than pretending the password is wrong")
    void patientRoleIsNotImplemented() throws Exception {
        // Someone told "wrong password" for an account that could never work
        // will simply keep trying.
        mvc.perform(post("/api/auth/login/patient")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"email\":\"someone@example.invalid\",\"password\":\"x\",\"mode\":\"email\"}"))
                .andExpect(status().isNotImplemented())
                .andExpect(jsonPath("$.message").value(
                        org.hamcrest.Matchers.containsString("not built yet")));
    }

    @Test
    @DisplayName("an unknown role is 404")
    void unknownRoleIsNotFound() throws Exception {
        mvc.perform(post("/api/auth/login/wizard")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"email\":\"a@b.c\",\"password\":\"x\"}"))
                .andExpect(status().isNotFound());
    }

    @Test
    @DisplayName("a missing password is a validation failure naming the field")
    void missingPasswordIsBadRequest() throws Exception {
        mvc.perform(post("/api/auth/login/faculty")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"email\":\"" + FACULTY_EMAIL + "\",\"mode\":\"email\"}"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.fieldErrors.password").exists());
    }

    @Test
    @DisplayName("a forged token is refused")
    void forgedTokenIsRefused() throws Exception {
        mvc.perform(get("/api/me").header("Authorization", "Bearer not.a.real.token"))
                .andExpect(status().isUnauthorized());
    }

    @Test
    @DisplayName("HTTP Basic still works, so scripts and curl do not need a token")
    void basicAuthStillWorks() throws Exception {
        mvc.perform(get("/api/me").with(request -> {
            String credentials = java.util.Base64.getEncoder()
                    .encodeToString((FACULTY_EMAIL + ":" + PASSWORD).getBytes());
            request.addHeader("Authorization", "Basic " + credentials);
            return request;
        })).andExpect(status().isOk())
                .andExpect(jsonPath("$.email").value(FACULTY_EMAIL));
    }
}
