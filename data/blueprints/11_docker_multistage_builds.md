# Module: Docker Multi-Stage Build Optimization

## Metadata
- Module ID: blueprint_11_docker_multistage
- Difficulty Level: 2
- Prerequisites: Docker, Python 3.11, Poetry

## Architecture Pattern
Construct an optimized multi-stage Dockerfile that cleanly decouples compilation dependencies from the production runtime image. The builder stage utilizes a full Debian image to install build tools (gcc, g++, git), configure Poetry, compile native C-extensions, and package wheels into an isolated virtual environment. The final runtime stage copies only the compiled virtual environment and application source code onto a clean, minimal debian-slim image. The container runs as an unprivileged non-root user (UID 10001) to eliminate container privilege escalation risks.

## Explicit Tradeoffs
- Latency Impact: Zero impact on runtime execution latency; reduces CI/CD image deployment and container pull times by over 60% across build pipelines.
- Memory Footprint: Reduces the final container image footprint from ~1.8 GB (full build toolchain) down to <350 MB on disk.
- Operational Complexity: Debugging production runtime containers requires external diagnostic tooling or ephemeral debug sidecars due to the absence of build utilities, compilers, and shells.

## Verification Metric
Final production Docker image size is strictly below 400 MB; container image security scans detect zero high or critical CVE vulnerabilities.
