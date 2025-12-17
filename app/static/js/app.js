class PDFConverterApp {
    constructor() {
        this.currentTaskId = null;
        this.currentPage = 1;
        this.totalPages = 1;
        this.zoomLevel = 100;
        this.statusCheckInterval = null;

        this.initializeElements();
        this.attachEventListeners();
    }

    initializeElements() {
        // Upload elements
        this.uploadContainer = document.getElementById('uploadContainer');
        this.uploadArea = document.getElementById('uploadArea');
        this.uploadButton = document.getElementById('uploadButton');
        this.fileInput = document.getElementById('fileInput');

        // Settings elements
        this.settingsContainer = document.getElementById('settingsContainer');
        this.grayLevelsSelect = document.getElementById('grayLevels');
        this.convertButton = document.getElementById('convertButton');

        // Progress elements
        this.progressSection = document.getElementById('progressSection');
        this.progressFill = document.getElementById('progressFill');
        this.progressText = document.getElementById('progressText');

        // Preview elements
        this.previewSection = document.getElementById('previewSection');
        this.originalImage = document.getElementById('originalImage');
        this.convertedImage = document.getElementById('convertedImage');
        this.prevPageButton = document.getElementById('prevPage');
        this.nextPageButton = document.getElementById('nextPage');
        this.currentPageSpan = document.getElementById('currentPage');
        this.totalPagesSpan = document.getElementById('totalPages');
        this.zoomInButton = document.getElementById('zoomIn');
        this.zoomOutButton = document.getElementById('zoomOut');
        this.zoomLevelSpan = document.getElementById('zoomLevel');

        // Download elements
        this.downloadButton = document.getElementById('downloadButton');
        this.newConvertButton = document.getElementById('newConvertButton');

        // Error elements
        this.errorSection = document.getElementById('errorSection');
        this.errorMessage = document.getElementById('errorMessage');
        this.retryButton = document.getElementById('retryButton');

        // Loading overlay
        this.loadingOverlay = document.getElementById('loadingOverlay');
    }

    attachEventListeners() {
        // Upload events
        this.uploadButton.addEventListener('click', () => this.fileInput.click());
        this.fileInput.addEventListener('change', (e) => this.handleFileSelect(e));
        this.uploadArea.addEventListener('click', () => this.fileInput.click());

        // Drag and drop events
        this.uploadArea.addEventListener('dragover', (e) => this.handleDragOver(e));
        this.uploadArea.addEventListener('dragleave', (e) => this.handleDragLeave(e));
        this.uploadArea.addEventListener('drop', (e) => this.handleFileDrop(e));

        // Convert events
        this.convertButton.addEventListener('click', () => this.startConversion());

        // Navigation events
        this.prevPageButton.addEventListener('click', () => this.navigatePage(-1));
        this.nextPageButton.addEventListener('click', () => this.navigatePage(1));
        this.zoomInButton.addEventListener('click', () => this.changeZoom(25));
        this.zoomOutButton.addEventListener('click', () => this.changeZoom(-25));

        // Download events
        this.downloadButton.addEventListener('click', () => this.downloadConvertedPDF());
        this.newConvertButton.addEventListener('click', () => this.resetApp());

        // Retry event
        this.retryButton.addEventListener('click', () => this.resetApp());
    }

    handleDragOver(e) {
        e.preventDefault();
        e.stopPropagation();
        this.uploadArea.classList.add('dragover');
    }

    handleDragLeave(e) {
        e.preventDefault();
        e.stopPropagation();
        this.uploadArea.classList.remove('dragover');
    }

    handleFileDrop(e) {
        e.preventDefault();
        e.stopPropagation();
        this.uploadArea.classList.remove('dragover');

        const files = e.dataTransfer.files;
        if (files.length > 0) {
            this.processFile(files[0]);
        }
    }

    handleFileSelect(e) {
        const file = e.target.files[0];
        if (file) {
            this.processFile(file);
        }
    }

    processFile(file) {
        // Validate file type
        if (file.type !== 'application/pdf') {
            alert('⚠️ 请选择 PDF 文件');
            return;
        }

        // Validate file size (50MB)
        const maxSize = 50 * 1024 * 1024;
        if (file.size > maxSize) {
            const fileSizeMB = (file.size / (1024 * 1024)).toFixed(2);
            alert(`⚠️ 文件大小超过限制！

当前文件: ${fileSizeMB} MB
最大限制: 50 MB

请选择更小的文件。`);
            return;
        }

        // Store file reference
        this.selectedFile = file;

        // Update UI to show settings and display filename
        this.showSettings();
    }

    showSettings() {
        // Display filename in settings container
        let filenameDisplay = document.getElementById('selectedFilename');
        if (!filenameDisplay) {
            filenameDisplay = document.createElement('div');
            filenameDisplay.id = 'selectedFilename';
            filenameDisplay.className = 'selected-filename';
            this.settingsContainer.insertBefore(filenameDisplay, this.settingsContainer.firstChild);
        }
        
        const fileSizeMB = (this.selectedFile.size / (1024 * 1024)).toFixed(2);
        filenameDisplay.innerHTML = `📄 <strong>${this.selectedFile.name}</strong> <span class="file-size">(${fileSizeMB} MB)</span>`;
        
        this.settingsContainer.style.display = 'block';
        this.settingsContainer.scrollIntoView({ behavior: 'smooth' });
    }

    async startConversion() {
        if (!this.selectedFile) {
            this.showError('请先选择文件');
            return;
        }

        this.showLoading();

        try {
            const formData = new FormData();
            formData.append('file', this.selectedFile);
            formData.append('gray_levels', this.grayLevelsSelect.value);

            const response = await fetch('/api/convert', {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || '转换失败');
            }

            const result = await response.json();
            this.currentTaskId = result.task_id;

            // Start status checking
            this.hideLoading();
            this.showProgress();
            this.startStatusChecking();

        } catch (error) {
            this.hideLoading();
            this.showError(error.message);
        }
    }

    startStatusChecking() {
        this.statusCheckInterval = setInterval(() => {
            this.checkStatus();
        }, 1000);
    }

    async checkStatus() {
        if (!this.currentTaskId) return;

        try {
            const response = await fetch(`/api/status/${this.currentTaskId}`);
            if (!response.ok) {
                throw new Error('状态检查失败');
            }

            const status = await response.json();
            this.updateProgress(status);

            if (status.status === 'completed') {
                this.onConversionCompleted(status);
            } else if (status.status === 'error') {
                this.onConversionError(status.error);
            }

        } catch (error) {
            console.error('Status check error:', error);
        }
    }

    updateProgress(status) {
        const progressPercentage = status.progress;
        this.progressFill.style.width = `${progressPercentage}%`;

        let statusText = '转换中...';
        if (status.status === 'processing') {
            statusText = '准备中...';
        } else if (status.status === 'converting') {
            statusText = `转换中... ${progressPercentage}%`;
        } else if (status.status === 'completed') {
            statusText = '转换完成！';
        }

        this.progressText.textContent = statusText;
    }

    onConversionCompleted(status) {
        clearInterval(this.statusCheckInterval);
        this.totalPages = status.page_count;

        // Update UI
        this.totalPagesSpan.textContent = this.totalPages;
        this.currentPage = 1;
        this.currentPageSpan.textContent = this.currentPage;

        // Enable navigation
        this.updateNavigationButtons();

        // Load preview images
        this.loadPreviewImages();

        // Show preview section and enable download
        this.progressSection.style.display = 'none';
        this.previewSection.style.display = 'block';
        this.downloadButton.disabled = false;
    }

    onConversionError(error) {
        clearInterval(this.statusCheckInterval);
        this.showError(error || '转换过程中发生错误');
    }

    async loadPreviewImages() {
        if (!this.currentTaskId) return;

        try {
            // Load original image
            const originalResponse = await fetch(
                `/api/preview/${this.currentTaskId}/${this.currentPage}?preview_type=original`
            );
            if (originalResponse.ok) {
                const originalBlob = await originalResponse.blob();
                this.originalImage.src = URL.createObjectURL(originalBlob);
            }

            // Load converted image
            const convertedResponse = await fetch(
                `/api/preview/${this.currentTaskId}/${this.currentPage}?preview_type=converted`
            );
            if (convertedResponse.ok) {
                const convertedBlob = await convertedResponse.blob();
                this.convertedImage.src = URL.createObjectURL(convertedBlob);
            }

        } catch (error) {
            console.error('Preview loading error:', error);
        }
    }

    navigatePage(direction) {
        const newPage = this.currentPage + direction;
        if (newPage >= 1 && newPage <= this.totalPages) {
            this.currentPage = newPage;
            this.currentPageSpan.textContent = this.currentPage;
            this.updateNavigationButtons();
            this.loadPreviewImages();
        }
    }

    updateNavigationButtons() {
        this.prevPageButton.disabled = this.currentPage <= 1;
        this.nextPageButton.disabled = this.currentPage >= this.totalPages;
    }

    changeZoom(delta) {
        const newZoom = this.zoomLevel + delta;
        if (newZoom >= 50 && newZoom <= 200) {
            this.zoomLevel = newZoom;
            this.zoomLevelSpan.textContent = `${this.zoomLevel}%`;

            // Apply zoom to images
            const scale = this.zoomLevel / 100;
            this.originalImage.style.transform = `scale(${scale})`;
            this.convertedImage.style.transform = `scale(${scale})`;
        }
    }

    async downloadConvertedPDF() {
        if (!this.currentTaskId) return;

        try {
            const response = await fetch(`/api/download/${this.currentTaskId}`);
            if (!response.ok) {
                throw new Error('下载失败');
            }

            const blob = await response.blob();
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `converted_${this.currentTaskId}.pdf`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);

        } catch (error) {
            this.showError('下载失败：' + error.message);
        }
    }

    showProgress() {
        this.progressSection.style.display = 'block';
        this.progressSection.scrollIntoView({ behavior: 'smooth' });
    }

    showError(message) {
        this.errorMessage.textContent = message;
        this.errorSection.style.display = 'block';
        this.errorSection.scrollIntoView({ behavior: 'smooth' });

        // Hide other sections
        this.settingsContainer.style.display = 'none';
        this.progressSection.style.display = 'none';
        this.previewSection.style.display = 'none';
    }

    showLoading() {
        this.loadingOverlay.style.display = 'flex';
    }

    hideLoading() {
        this.loadingOverlay.style.display = 'none';
    }

    resetApp() {
        // Clear intervals
        if (this.statusCheckInterval) {
            clearInterval(this.statusCheckInterval);
            this.statusCheckInterval = null;
        }

        // Reset state
        this.currentTaskId = null;
        this.currentPage = 1;
        this.totalPages = 1;
        this.zoomLevel = 100;
        this.selectedFile = null;

        // Reset form
        this.fileInput.value = '';
        this.grayLevelsSelect.value = '2';

        // Hide all sections
        this.settingsContainer.style.display = 'none';
        this.progressSection.style.display = 'none';
        this.previewSection.style.display = 'none';
        this.errorSection.style.display = 'none';

        // Reset zoom
        this.zoomLevelSpan.textContent = '100%';
        this.originalImage.style.transform = 'scale(1)';
        this.convertedImage.style.transform = 'scale(1)';
        this.originalImage.src = '';
        this.convertedImage.src = '';

        // Scroll to top
        window.scrollTo({ top: 0, behavior: 'smooth' });
    }
}

// Initialize app when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    new PDFConverterApp();
});