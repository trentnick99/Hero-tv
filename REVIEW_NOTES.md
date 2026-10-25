# Review of the ChatGPT revision (v0.2)

Kept from the revision: LAN-bind refusal, request-size and input validation, security headers, stricter Range handling, extra tests.

Fixed during review (each reproduced before fixing, each now covered by a test unless noted):
- Security headers were sent twice on JSON responses.
- A rejected oversized POST left its body on the keep-alive connection, so it was parsed as a second request.
- POSTs were accepted as text/plain from foreign origins and with foreign Host headers (cross-site / DNS-rebinding could mark media unplayable).
- Rescanning never restored files marked unplayable by transient playback errors, contrary to the README.
- An unmounted or empty media folder marked the whole library missing and wiped every channel's future schedule.
- Guide: the 10th channel row could be clipped off-screen, the column maths did not match the 17vw channel column, and overlapping tune() calls could race (not render-tested).
- DB connection leak in the 5-minute maintainer loop on errors; test sockets and files not closed; README test count out of date.
- systemd unit: waits for the media mount and time sync, adds NoNewPrivileges/PrivateTmp.

Known and left alone: shuffle can repeat a title across a cycle boundary; a SystemExit from the LAN guard makes systemd restart-loop;
symlinked media folders are not followed; unclosed in-memory SQLite connections in some tests warn on Python 3.13 only (cannot reproduce here).
