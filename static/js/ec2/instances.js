(function () {
    const root = document.getElementById('terminal-app');
    if (!root) return;

    const wsUrl = root.dataset.wsUrl;
    const detailUrl = root.dataset.detailUrl;
    const statusEl = root.querySelector('.terminal-status');
    const fullscreenBtn = root.querySelector('[data-action="fullscreen"]');
    const disconnectBtn = root.querySelector('[data-action="disconnect"]');
    const host = root.querySelector('.terminal-host');

    const term = new Terminal({
        cursorBlink: true,
        convertEol: true,
        scrollback: 5000,
        fontFamily: 'Menlo, Consolas, "Liberation Mono", monospace',
        fontSize: 14,
        theme: { background: '#000000', foreground: '#e5e7eb' },
    });
    const fitAddon = new FitAddon.FitAddon();
    term.loadAddon(fitAddon);
    term.open(host);
    fitAddon.fit();

    const ws = new WebSocket(wsUrl);
    ws.binaryType = 'arraybuffer';
    const encoder = new TextEncoder();

    function setStatus(text, color) {
        if (!statusEl) return;
        statusEl.textContent = text;
        statusEl.style.color = color || '';
    }

    ws.onopen = () => {
        setStatus('connected', '#10b981');
        term.focus();
        ws.send(JSON.stringify({ type: 'resize', rows: term.rows, cols: term.cols }));
    };
    ws.onmessage = (e) => {
        if (e.data instanceof ArrayBuffer) {
            term.write(new Uint8Array(e.data));
        } else {
            term.write(e.data);
        }
    };
    ws.onclose = () => {
        setStatus('disconnected', '#ef4444');
        term.write('\r\n\x1b[31m[disconnected]\x1b[0m\r\n');
    };
    ws.onerror = () => {
        setStatus('error', '#ef4444');
        term.write('\r\n\x1b[31m[connection error]\x1b[0m\r\n');
    };

    // Send keystrokes as binary so the server never has to disambiguate raw
    // input from JSON control messages (digits would otherwise parse as valid
    // JSON and get dropped).
    term.onData((data) => {
        if (ws.readyState === WebSocket.OPEN) ws.send(encoder.encode(data));
    });
    term.onResize(({ rows, cols }) => {
        if (ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: 'resize', rows, cols }));
        }
    });

    function refit() {
        try { fitAddon.fit(); } catch (_) { /* not yet visible */ }
    }
    window.addEventListener('resize', refit);

    function setFullscreen(on) {
        root.classList.toggle('fullscreen', on);
        if (fullscreenBtn) {
            fullscreenBtn.textContent = on ? 'Exit fullscreen' : 'Fullscreen';
        }
        // Wait for layout, then refit so xterm matches the new size.
        requestAnimationFrame(refit);
    }
    if (fullscreenBtn) {
        fullscreenBtn.addEventListener('click', () => {
            setFullscreen(!root.classList.contains('fullscreen'));
        });
    }
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && root.classList.contains('fullscreen')) {
            setFullscreen(false);
        }
    });

    if (disconnectBtn) {
        disconnectBtn.addEventListener('click', () => {
            ws.close();
            window.location.href = detailUrl;
        });
    }
})();
