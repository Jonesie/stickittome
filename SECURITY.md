# Security Policy

## Supported versions

This project is in its initial public release. Security fixes will be issued
for the latest tagged release. Older versions will not receive patches unless
specifically requested.

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | ✅ latest          |
| < 0.1   | ❌                 |

## Reporting a vulnerability

Please **do not** open a public issue for security vulnerabilities.

Email the maintainers at **peter@jonesie.net.nz** (or use GitHub's
[private vulnerability reporting][gh-private] if enabled for this repository)
and include:

- A description of the issue and its impact.
- Steps to reproduce, ideally with a minimal `.pose.json` or Python snippet.
- The version of `stickittome` you're using, plus Python and
  Pillow versions.

You can expect an acknowledgement within 7 days. We will follow up with a
plan and, if confirmed, a fix released as a patch version. We are happy to
credit reporters in the CHANGELOG unless you'd prefer to remain anonymous.

## Scope

This is a desktop drawing tool with a single third-party dependency
([`Pillow`](https://python-pillow.org)). Realistic security concerns are:

- Image-parser issues in Pillow (we delegate all PNG / JPG handling to it;
  ours is just data-model + GUI code).
- Path-handling bugs in the file dialogs (we use `os.path.abspath` and trust
  paths from the user's own file dialogs).
- Anything introduced by future dependencies (we currently only ship
  Pillow; additions will be reviewed).

[gh-private]: https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-vulnerabilities/privately-reporting-a-security-vulnerability