# emgteach 3.7.2 — the classroom broadcast on ports 8080 and 8443, changeable in a file

A patch for the November practicals, which follow the session on the
students' phones.

**3.7.0 remains the version the article describes.** No analysis, no EDF
format and no calculation changes. Recordings made with 3.7.0 and 3.7.1 open
and read as before.

## The ports

- **New defaults: 8080 for the page, 8443 for the data.** They were 8070 and
  8071. The follower link carries the page port and the page takes the data
  port from the server, so the students still only open the link or scan the
  QR.
- **The ports can be changed in `difusion.txt`, next to the application.**
  Which ports get through depends on the network, and that varies from one
  place to another, so they are not fixed in the application. A laboratory
  writes them once:

  ```
  # Ports of the broadcast to the phones
  pagina = 8080
  datos = 8443
  ```

  Without the file, 8080 and 8443. The file is separate from `bitalino.txt`:
  the ports are the same on every station of the laboratory, the board's
  address is each station's own. A line that cannot be used (not a number,
  outside 1-65535, the two ports equal, or another name) puts back both
  defaults, and the log says which line at start.
- **A busy port is named.** If another program holds one of the ports, the
  warning says which, and that other ports can be written in `difusion.txt`.
- **«Nobody has joined» mentions the ports** in one sentence.

## Before the practical

- **The Windows firewall.** A rule opened for 8070 and 8071 does not cover the
  new ports. The laboratory kit's `LEEME.txt` gives the command for 8080 and
  8443.
- **Port 8443 is the usual HTTPS port, and the data connection is not
  encrypted.** A network that looks only at the port number lets it through.
  One that inspects the protocol would cut it. Then the page loads on the
  phone but stays at «connecting…» with no data, the computer keeps counting
  0 followers, and after 90 s the «nobody has joined» warning appears. That
  is told apart from a closed port because with a closed port the page does
  not load at all. In that case, another data port in `difusion.txt`.

## How it was tested

**By the automated suite**, 1419 tests: the reading of `difusion.txt` (lines
that are good, lines that are not, the file next to the frozen executable), a
port held by another program named by the server, and the warnings.

**Not yet on the university Wi-Fi.** The five-minute check with the simulated
board and a phone on that network is on the laboratory checklist.

## The Windows executable

The release carries `emgteach-v3.7.2-windows-x64.exe`. GitHub Actions builds
it from this tag and self-tests it headless, and GitHub attests where it was
built.

- **It is not signed.** Windows may show «Windows protected your PC»: choose
  *More info → Run anyway*.
- **Its SHA-256** is at the end of these notes. In PowerShell,
  `Get-FileHash .\emgteach-v3.7.2-windows-x64.exe -Algorithm SHA256` has to
  print the same value.
- **To check where it was built**:
  `gh attestation verify emgteach-v3.7.2-windows-x64.exe --repo aagisto-maker/emgteach`.

The Zenodo record archives the source code of the tag, not the executable.

See [`CHANGELOG.md`](../CHANGELOG.md) for every change.
