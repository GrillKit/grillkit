# Security Policy

## Supported Versions

We currently provide security updates for the following versions:

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |

## Reporting a Vulnerability

If you discover a security vulnerability in GrillKit, please report it responsibly.

**Please do NOT report security vulnerabilities through public GitHub issues.**

Instead, please use GitHub Security Advisory: https://github.com/yourusername/grillkit/security/advisories/new

Include the following information:
- Description of the vulnerability
- Steps to reproduce (if applicable)
- Potential impact
- Suggested fix (if any)

## What to Expect

- **Acknowledgment**: Within 48 hours of receiving your report
- **Investigation**: We will investigate and validate the issue
- **Timeline**: We aim to provide updates every 5-7 days
- **Fix**: Once fixed, we will release a security patch
- **Credit**: You will be credited (if desired) in the security advisory

## Security Best Practices for Users

1. **API Keys**: Never commit API keys to version control. Use `data/config.json` (which is gitignored)
2. **Local Deployment**: This tool is designed for local/self-hosted use
3. **Regular Updates**: Keep dependencies updated: `uv sync --upgrade`
4. **Docker**: Use provided Docker setup for isolation

## Known Security Considerations

- AI provider API keys are stored locally in `data/config.json`
- Interview data is stored locally in SQLite
- No authentication system (designed for single-user local use)
- WebSocket connections are unencrypted over HTTP (use HTTPS in production with reverse proxy)
