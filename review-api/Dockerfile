# The review API as a container, so a demonstration machine needs Docker and
# nothing else -- no JDK, no Maven, no toolchain to get wrong an hour before a
# panel.
#
# Two stages: Maven builds the jar, and the image that ships carries only a JRE
# and that jar. The build tooling is several hundred megabytes and has no reason
# to be on the running machine.

# ---------------------------------------------------------------------------
# build
# ---------------------------------------------------------------------------
FROM maven:3.9-eclipse-temurin-21 AS build

WORKDIR /build

# Dependencies resolve from the pom alone, in their own layer. Editing a source
# file then costs a recompile rather than another download of the internet.
COPY pom.xml .
RUN mvn -B -q dependency:go-offline

COPY src ./src

# Tests are skipped here on purpose. They run against a real PostgreSQL and roll
# back, which is the right design for them and the wrong thing to require of an
# image build that has no database. `./mvnw test` is where they belong.
RUN mvn -B -q clean package -DskipTests

# ---------------------------------------------------------------------------
# run
# ---------------------------------------------------------------------------
FROM eclipse-temurin:21-jre

WORKDIR /app

# curl is here for the health check, and for nothing else.
RUN apt-get update \
    && apt-get install --no-install-recommends -y curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=build /build/target/*.jar app.jar

# The rendered ECGs are referenced in the database by a path relative to the
# repository root, so that root has to exist somewhere. Compose mounts the
# images underneath this.
ENV CARDIO_REPO_ROOT=/repo

# 8080 inside the container. The host port is chosen in compose, because the
# clash that made this project pick 8090 is a property of the host.
ENV REVIEW_API_PORT=8080
EXPOSE 8080

# A container that dies on a bad configuration should say so and stop, not
# restart forever. Compose is told not to restart it.
ENTRYPOINT ["java", "-XX:MaxRAMPercentage=75", "-jar", "/app/app.jar"]
