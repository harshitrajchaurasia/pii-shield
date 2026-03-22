        // ============================================
        // API Status Polling - for instant routing decisions
        // ============================================
        let apiIsAvailable = null;  // null = unknown, true = online, false = offline
        let apiStatusPollInterval = null;
        const API_STATUS_POLL_INTERVAL = 60000;  // Poll every 60 seconds

        async function checkApiStatus() {
            const badge = document.getElementById('api-status-badge');
            const text = document.getElementById('api-status-text');
            
            try {
                const controller = new AbortController();
                const timeoutId = setTimeout(() => controller.abort(), 5000);  // 5 sec timeout
                
                const response = await fetch('/api/status', { 
                    signal: controller.signal,
                    cache: 'no-store'
                });
                clearTimeout(timeoutId);
                
                if (response.ok) {
                    const data = await response.json();
                    apiIsAvailable = data.api_available;
                    
                    if (apiIsAvailable) {
                        badge.className = 'api-status-badge online';
                        text.textContent = 'API Online';
                        badge.title = `API Online (${data.response_time_ms}ms)`;
                    } else {
                        badge.className = 'api-status-badge offline';
                        text.textContent = 'Local Mode';
                        badge.title = 'API unavailable - using local processing';
                    }
                } else {
                    throw new Error('Status check failed');
                }
            } catch (error) {
                // If we can't reach the status endpoint, assume local mode
                apiIsAvailable = false;
                badge.className = 'api-status-badge offline';
                text.textContent = 'Local Mode';
                badge.title = 'Running in local processing mode';
            }
        }

        // Start API status polling on page load
        function initApiStatusPolling() {
            // Check immediately on page load
            checkApiStatus();
            
            // Then poll every 60 seconds
            apiStatusPollInterval = setInterval(checkApiStatus, API_STATUS_POLL_INTERVAL);
        }

        // Initialize on page load
        document.addEventListener('DOMContentLoaded', initApiStatusPolling);

        // ============================================
        // Theme Toggle
        // ============================================
        function initTheme() {
            const savedTheme = localStorage.getItem('theme');
            if (savedTheme) {
                document.documentElement.setAttribute('data-theme', savedTheme);
                updateThemeIcon(savedTheme);
            }
        }

        function updateThemeIcon(theme) {
            const toggle = document.getElementById('theme-toggle');
            const sunIcon = toggle.querySelector('.icon-sun');
            const moonIcon = toggle.querySelector('.icon-moon');
            
            if (theme === 'dark') {
                sunIcon.style.display = 'block';
                moonIcon.style.display = 'none';
            } else {
                sunIcon.style.display = 'none';
                moonIcon.style.display = 'block';
            }
        }

        function toggleTheme() {
            const currentTheme = document.documentElement.getAttribute('data-theme');
            let newTheme;
            
            if (currentTheme === 'dark') {
                newTheme = 'light';
            } else if (currentTheme === 'light') {
                newTheme = 'dark';
            } else {
                // No theme set, check system preference
                newTheme = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'light' : 'dark';
            }
            
            document.documentElement.setAttribute('data-theme', newTheme);
            localStorage.setItem('theme', newTheme);
            updateThemeIcon(newTheme);
        }

        document.getElementById('theme-toggle').addEventListener('click', toggleTheme);
        initTheme();

        document.querySelectorAll('.toggle-tab').forEach(tab => {
            tab.addEventListener('click', () => {
                document.querySelectorAll('.toggle-tab').forEach(t => t.classList.remove('active'));
                document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
                tab.classList.add('active');
                document.getElementById(tab.dataset.tab + '-panel').classList.add('active');
            });
        });

        const uploadZone = document.getElementById('upload-zone');
        const fileInput = document.getElementById('file-input');

        if (uploadZone && fileInput) {
            uploadZone.addEventListener('click', () => fileInput.click());
            uploadZone.addEventListener('dragover', (e) => { e.preventDefault(); uploadZone.classList.add('dragover'); });
            uploadZone.addEventListener('dragleave', () => uploadZone.classList.remove('dragover'));
            uploadZone.addEventListener('drop', (e) => {
                e.preventDefault();
                uploadZone.classList.remove('dragover');
                if (e.dataTransfer.files.length) { fileInput.files = e.dataTransfer.files; handleFileSelect(); }
            });
            fileInput.addEventListener('change', handleFileSelect);
        }

        // Live character counter
        const inputText = document.getElementById('input-text');
        const inputCounter = document.getElementById('input-counter');
        inputText.addEventListener('input', () => {
            const len = inputText.value.length;
            inputCounter.textContent = `${len.toLocaleString()} / 100,000 characters`;
            inputCounter.style.color = len > 90000 ? '#e74c3c' : 'var(--text-secondary)';
        });

        // Button event bindings (CSP-compliant, no inline handlers)
        document.getElementById('paste-btn').addEventListener('click', () => pasteFromClipboard());
        document.querySelectorAll('[data-example]').forEach(btn => {
            btn.addEventListener('click', () => loadExample(parseInt(btn.dataset.example)));
        });
        document.getElementById('redact-btn').addEventListener('click', () => redactText());

        const resetFileBtn = document.getElementById('reset-file-btn');
        if (resetFileBtn) resetFileBtn.addEventListener('click', () => resetFileUpload());
        const processBtn = document.getElementById('process-btn');
        if (processBtn) processBtn.addEventListener('click', () => processFile());
        const downloadResultBtn = document.getElementById('download-result-btn');
        if (downloadResultBtn) downloadResultBtn.addEventListener('click', () => downloadResult());
        const processAnotherBtn = document.getElementById('process-another-btn');
        if (processAnotherBtn) processAnotherBtn.addEventListener('click', () => resetFileUpload());

        const copyResultBtn = document.getElementById('copy-result-btn');
        if (copyResultBtn) copyResultBtn.addEventListener('click', () => copyResult());
        const downloadTxtBtn = document.getElementById('download-txt-btn');
        if (downloadTxtBtn) downloadTxtBtn.addEventListener('click', () => downloadResultAsTxt());

        let currentJobId = null;
        let selectedColumns = [];
        let statusPollInterval = null;

        function showToast(message, type = 'success') {
            const container = document.getElementById('toast-container');
            const toast = document.createElement('div');
            toast.className = `toast ${type}`;
            toast.innerHTML = `
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="${type === 'success' ? 'var(--success)' : 'var(--danger)'}" stroke-width="2">
                    ${type === 'success' ? '<path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/>' : '<circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/>'}
                </svg>
                <span class="toast-msg"></span>
                <button class="toast-close">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
                </button>
            `;
            // Use textContent for user message to prevent XSS
            toast.querySelector('.toast-msg').textContent = message;
            toast.querySelector('.toast-close').addEventListener('click', () => toast.remove());
            container.appendChild(toast);
            setTimeout(() => toast.remove(), 5000);
        }

        const examples = [
            "Help me write a complaint letter to my bank. My name is Rajesh Kumar, Aadhaar: 1234 5678 9012, PAN: ABCDE1234F, email: rajesh.kumar@gmail.com, phone: +91 98765 43210. The issue is with my account 50100123456789, IFSC: HDFC0001234.",
            "Review my resume and suggest improvements: John Smith, john.smith@email.com, (555) 123-4567, SSN: 123-45-6789, DOB: March 15, 1990. I live at 123 Main Street, New York, NY 10001. Currently working at Acme Corp.",
            "Summarize my bank dispute: My credit card 4532-1234-5678-9012 was charged Rs. 45,000 on 15/03/2025. My UPI ID is rajesh@okicici. Contact me at rajesh.k@gmail.com or +91 87654 32100. Account holder: Rajesh Kumar."
        ];
        function loadExample(index) {
            document.getElementById('input-text').value = examples[index];
        }

        async function redactText() {
            const text = document.getElementById('input-text').value;
            if (!text.trim()) { showToast('Please enter some text to process', 'error'); return; }
            const MAX_TEXT_LENGTH = 100000;
            if (text.length > MAX_TEXT_LENGTH) {
                showToast(`Text too long (${(text.length/1000).toFixed(0)}KB). Maximum is 100KB.`, 'error');
                return;
            }

            const btn = document.getElementById('redact-btn');
            btn.disabled = true;
            btn.innerHTML = '<span class="spinner"></span> Processing...';

            try {
                const fastMode = document.getElementById('fast-mode-text').checked;
                const response = await fetch('/api/redact-text', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ text: text, fast_mode: fastMode })
                });

                const data = await response.json();
                
                // Check for error response
                if (!response.ok) {
                    throw new Error(data.detail || data.message || 'Processing failed');
                }
                
                document.getElementById('output-text').textContent = data.redacted_text || '';
                document.getElementById('stat-redactions').textContent = data.redaction_count || 0;
                document.getElementById('stat-time').textContent = (data.processing_time_ms || 0).toFixed(1) + 'ms';
                document.getElementById('stat-mode').textContent = fastMode ? 'Fast' : 'Full';
                document.getElementById('empty-state').classList.add('hidden');
                document.getElementById('text-result').classList.remove('hidden');
                showToast(`Successfully redacted ${data.redaction_count || 0} items`);
            } catch (error) {
                showToast('Error: ' + error.message, 'error');
            } finally {
                btn.disabled = false;
                btn.innerHTML = `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg> Process & Redact`;
            }
        }

        function copyResult() {
            const text = document.getElementById('output-text').textContent;
            if (navigator.clipboard && navigator.clipboard.writeText) {
                navigator.clipboard.writeText(text)
                    .then(() => showToast('Copied to clipboard'))
                    .catch(() => {
                        const range = document.createRange();
                        range.selectNodeContents(document.getElementById('output-text'));
                        window.getSelection().removeAllRanges();
                        window.getSelection().addRange(range);
                        showToast('Text selected - press Ctrl+C to copy', 'warning');
                    });
            } else {
                const ta = document.createElement('textarea');
                ta.value = text;
                ta.style.position = 'fixed';
                ta.style.opacity = '0';
                document.body.appendChild(ta);
                ta.select();
                document.execCommand('copy');
                document.body.removeChild(ta);
                showToast('Copied to clipboard');
            }
        }

        async function pasteFromClipboard() {
            try {
                if (navigator.clipboard && navigator.clipboard.readText) {
                    const text = await navigator.clipboard.readText();
                    document.getElementById('input-text').value = text;
                    document.getElementById('input-text').dispatchEvent(new Event('input'));
                    showToast('Pasted from clipboard');
                } else {
                    showToast('Clipboard access not available - use Ctrl+V', 'warning');
                }
            } catch (e) {
                showToast('Clipboard access denied - use Ctrl+V instead', 'warning');
            }
        }

        function downloadResultAsTxt() {
            const text = document.getElementById('output-text').textContent;
            if (!text) { showToast('No result to download', 'error'); return; }
            const blob = new Blob([text], { type: 'text/plain' });
            const a = document.createElement('a');
            a.href = URL.createObjectURL(blob);
            a.download = 'redacted_output.txt';
            a.click();
            URL.revokeObjectURL(a.href);
            showToast('Downloaded redacted text');
        }

        async function handleFileSelect() {
            const file = fileInput.files[0];
            if (!file) return;
            if (file.size > 500 * 1024 * 1024) {
                showToast(`File too large (${(file.size / (1024*1024)).toFixed(1)}MB). Maximum is 500MB.`, 'error');
                fileInput.value = '';
                return;
            }

            const formData = new FormData();
            formData.append('file', file);

            try {
                const response = await fetch('/api/upload', { method: 'POST', body: formData });
                const data = await response.json();
                currentJobId = data.job_id;

                document.getElementById('file-name').textContent = data.filename;
                document.getElementById('file-meta').textContent = `${data.file_type.toUpperCase()} • Ready to process`;

                if (data.columns && data.columns.length > 0) {
                    document.getElementById('column-selection').classList.remove('hidden');
                    const columnsList = document.getElementById('columns-list');
                    columnsList.innerHTML = '';
                    selectedColumns = [];

                    data.columns.forEach(col => {
                        const chip = document.createElement('span');
                        chip.className = 'column-chip';
                        chip.textContent = col;
                        chip.onclick = () => {
                            chip.classList.toggle('selected');
                            if (chip.classList.contains('selected')) selectedColumns.push(col);
                            else selectedColumns = selectedColumns.filter(c => c !== col);
                        };
                        columnsList.appendChild(chip);
                    });
                } else {
                    document.getElementById('column-selection').classList.add('hidden');
                }

                uploadZone.classList.add('hidden');
                document.getElementById('file-options').classList.remove('hidden');
                document.getElementById('file-progress').classList.add('hidden');
                document.getElementById('file-result').classList.add('hidden');
            } catch (error) {
                showToast('Upload failed: ' + error.message, 'error');
            }
        }

        async function processFile() {
            if (!currentJobId) return;

            const btn = document.getElementById('process-btn');
            btn.disabled = true;
            btn.innerHTML = '<span class="spinner"></span> Starting...';

            const formData = new FormData();
            selectedColumns.forEach(col => formData.append('columns', col));
            formData.append('fast_mode', document.getElementById('fast-mode-file').checked);

            try {
                const response = await fetch(`/api/process/${currentJobId}`, { method: 'POST', body: formData });
                if (!response.ok) throw new Error('Processing failed');

                document.getElementById('file-options').classList.add('hidden');
                document.getElementById('file-progress').classList.remove('hidden');
                startStatusPolling();
            } catch (error) {
                showToast('Processing failed: ' + error.message, 'error');
                btn.disabled = false;
                btn.innerHTML = `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg> Process File`;
            }
        }

        let pollFailures = 0;
        function startStatusPolling() {
            pollFailures = 0;
            statusPollInterval = setInterval(async () => {
                try {
                    const response = await fetch(`/api/status/${currentJobId}`);
                    const data = await response.json();
                    pollFailures = 0;
                    updateStatus(data);
                    if (data.status === 'completed' || data.status === 'failed') clearInterval(statusPollInterval);
                } catch (error) {
                    pollFailures++;
                    if (pollFailures >= 5) {
                        clearInterval(statusPollInterval);
                        showToast('Lost connection to server. Please refresh and try again.', 'error');
                        resetFileUpload();
                    }
                }
            }, 1000);
        }
        window.addEventListener('beforeunload', () => {
            if (statusPollInterval) clearInterval(statusPollInterval);
        });

        function updateStatus(data) {
            document.getElementById('status-indicator').className = 'status-indicator ' + data.status;
            document.getElementById('status-text').textContent = data.status.charAt(0).toUpperCase() + data.status.slice(1);
            document.getElementById('status-message').textContent = data.message;
            const progressFill = document.getElementById('progress-fill');
            progressFill.style.width = data.progress + '%';
            progressFill.setAttribute('aria-valuenow', data.progress);
            document.getElementById('progress-pct').textContent = data.progress + '%';

            if (data.status === 'completed') {
                document.getElementById('file-progress').classList.add('hidden');
                document.getElementById('file-result').classList.remove('hidden');
                document.getElementById('result-filename').textContent = data.output_file;
                document.getElementById('result-message').textContent = 'Processing complete • Ready for download';
                showToast('File processed successfully');
            } else if (data.status === 'failed') {
                document.getElementById('file-progress').classList.add('hidden');
                showToast('Processing failed: ' + data.message, 'error');
                resetFileUpload();
            }
        }

        function downloadResult() {
            if (currentJobId) {
                window.location.href = `/api/download/${currentJobId}`;
                // Auto-delete file after download (zero data retention)
                const jobToDelete = currentJobId;
                setTimeout(() => {
                    fetch(`/api/job/${jobToDelete}`, { method: 'DELETE' })
                        .then(() => showToast('Your uploaded file has been deleted from the server', 'success'))
                        .catch(() => {});
                    resetFileUpload();
                }, 2000);
            }
        }

        function resetFileUpload() {
            currentJobId = null;
            selectedColumns = [];
            fileInput.value = '';
            uploadZone.classList.remove('hidden');
            document.getElementById('file-options').classList.add('hidden');
            document.getElementById('file-progress').classList.add('hidden');
            document.getElementById('file-result').classList.add('hidden');
            const btn = document.getElementById('process-btn');
            btn.disabled = false;
            btn.innerHTML = `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg> Process File`;
        }