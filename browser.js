const { ipcRenderer } = require('electron');

class NovaBrowser {
    constructor() {
        this.tabs = [];
        this.activeTabId = null;
        this.tabCounter = 0;
        
        this.initializeElements();
        this.attachEventListeners();
    }

    initializeElements() {
        this.tabsList = document.getElementById('tabsList');
        this.browserContainer = document.getElementById('browserContainer');
        this.emptyState = document.getElementById('emptyState');
        this.urlBar = document.getElementById('urlBar');
        this.backBtn = document.getElementById('backBtn');
        this.forwardBtn = document.getElementById('forwardBtn');
        this.refreshBtn = document.getElementById('refreshBtn');
        this.goBtn = document.getElementById('goBtn');
        this.newTabBtn = document.getElementById('newTabBtn');
        this.logoutBtn = document.getElementById('logoutBtn');
    }

    attachEventListeners() {
        this.newTabBtn.addEventListener('click', () => this.createNewTab());
        this.backBtn.addEventListener('click', () => this.navigateBack());
        this.forwardBtn.addEventListener('click', () => this.navigateForward());
        this.refreshBtn.addEventListener('click', () => this.refresh());
        this.goBtn.addEventListener('click', () => this.navigate());
        this.logoutBtn.addEventListener('click', () => this.logout());
        
        this.urlBar.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                this.navigate();
            }
        });
    }

    createNewTab(url = 'https://www.google.com') {
        // Security: Validate URL to only allow http and https protocols
        const urlLower = url.toLowerCase();
        if (!urlLower.startsWith('http://') && !urlLower.startsWith('https://')) {
            console.warn('Invalid URL protocol for new tab, defaulting to Google');
            url = 'https://www.google.com';
        }
        
        const tabId = `tab-${this.tabCounter++}`;
        
        // Create webview container
        const webviewContainer = document.createElement('div');
        webviewContainer.className = 'webview-container';
        webviewContainer.id = `container-${tabId}`;
        
        // Create webview
        const webview = document.createElement('webview');
        webview.src = url;
        webview.id = tabId;
        
        // Add event listeners to webview
        webview.addEventListener('did-start-loading', () => {
            this.updateNavigationButtons();
        });
        
        webview.addEventListener('did-stop-loading', () => {
            this.updateNavigationButtons();
            this.updateTabTitle(tabId);
        });
        
        webview.addEventListener('page-title-updated', () => {
            this.updateTabTitle(tabId);
        });
        
        webview.addEventListener('did-navigate', (e) => {
            if (this.activeTabId === tabId) {
                this.urlBar.value = e.url;
            }
        });
        
        webview.addEventListener('did-navigate-in-page', (e) => {
            if (this.activeTabId === tabId) {
                this.urlBar.value = e.url;
            }
        });
        
        webviewContainer.appendChild(webview);
        this.browserContainer.appendChild(webviewContainer);
        
        // Create tab item in sidebar
        const tabItem = document.createElement('div');
        tabItem.className = 'tab-item';
        tabItem.id = `item-${tabId}`;
        
        const tabTitle = document.createElement('div');
        tabTitle.className = 'tab-title';
        tabTitle.textContent = 'Loading...';
        
        const closeBtn = document.createElement('button');
        closeBtn.className = 'close-tab-btn';
        closeBtn.textContent = '×';
        closeBtn.onclick = (e) => {
            e.stopPropagation();
            this.closeTab(tabId);
        };
        
        tabItem.appendChild(tabTitle);
        tabItem.appendChild(closeBtn);
        
        tabItem.addEventListener('click', () => {
            this.switchToTab(tabId);
        });
        
        this.tabsList.appendChild(tabItem);
        
        // Add tab to array
        this.tabs.push({
            id: tabId,
            webview: webview,
            container: webviewContainer,
            tabItem: tabItem,
            title: 'New Tab'
        });
        
        // Switch to the new tab
        this.switchToTab(tabId);
        
        // Hide empty state
        this.emptyState.style.display = 'none';
    }

    switchToTab(tabId) {
        // Deactivate all tabs
        this.tabs.forEach(tab => {
            tab.container.classList.remove('active');
            tab.tabItem.classList.remove('active');
        });
        
        // Activate selected tab
        const tab = this.tabs.find(t => t.id === tabId);
        if (tab) {
            tab.container.classList.add('active');
            tab.tabItem.classList.add('active');
            this.activeTabId = tabId;
            
            // Update URL bar
            try {
                this.urlBar.value = tab.webview.getURL();
            } catch (e) {
                this.urlBar.value = '';
            }
            
            this.updateNavigationButtons();
        }
    }

    closeTab(tabId) {
        const tabIndex = this.tabs.findIndex(t => t.id === tabId);
        if (tabIndex === -1) return;
        
        const tab = this.tabs[tabIndex];
        
        // Remove DOM elements
        tab.container.remove();
        tab.tabItem.remove();
        
        // Remove from array
        this.tabs.splice(tabIndex, 1);
        
        // If closing active tab, switch to another tab
        if (this.activeTabId === tabId) {
            if (this.tabs.length > 0) {
                const nextTab = this.tabs[Math.max(0, tabIndex - 1)];
                this.switchToTab(nextTab.id);
            } else {
                this.activeTabId = null;
                this.emptyState.style.display = 'flex';
                this.urlBar.value = '';
            }
        }
    }

    updateTabTitle(tabId) {
        const tab = this.tabs.find(t => t.id === tabId);
        if (tab) {
            try {
                const title = tab.webview.getTitle() || 'New Tab';
                tab.title = title;
                const tabTitle = tab.tabItem.querySelector('.tab-title');
                if (tabTitle) {
                    tabTitle.textContent = title;
                }
            } catch (e) {
                // Webview not ready yet
            }
        }
    }

    navigate() {
        if (!this.activeTabId) {
            this.createNewTab();
        }
        
        const tab = this.tabs.find(t => t.id === this.activeTabId);
        if (tab) {
            let url = this.urlBar.value.trim();
            const urlLower = url.toLowerCase();
            
            // Security: Validate and sanitize URL to prevent malicious navigation
            // Only allow http and https protocols
            const dangerousProtocols = ['javascript:', 'data:', 'file:', 'vbscript:', 'about:', 'blob:'];
            for (const protocol of dangerousProtocols) {
                if (urlLower.startsWith(protocol)) {
                    console.warn('Blocked potentially malicious URL:', url);
                    return;
                }
            }
            
            // Add protocol if missing
            if (!urlLower.startsWith('http://') && !urlLower.startsWith('https://')) {
                // Check if it looks like a domain (contains a dot and no spaces)
                if (url.includes('.') && !url.includes(' ') && url.indexOf('.') > 0) {
                    url = 'https://' + url;
                } else {
                    // Treat as search query
                    url = 'https://www.google.com/search?q=' + encodeURIComponent(url);
                }
            }
            
            // Final validation: ensure URL starts with http or https (case insensitive)
            const finalUrlLower = url.toLowerCase();
            if (!finalUrlLower.startsWith('http://') && !finalUrlLower.startsWith('https://')) {
                console.warn('Invalid URL protocol:', url);
                return;
            }
            
            tab.webview.src = url;
        }
    }

    navigateBack() {
        const tab = this.tabs.find(t => t.id === this.activeTabId);
        if (tab && tab.webview.canGoBack()) {
            tab.webview.goBack();
        }
    }

    navigateForward() {
        const tab = this.tabs.find(t => t.id === this.activeTabId);
        if (tab && tab.webview.canGoForward()) {
            tab.webview.goForward();
        }
    }

    refresh() {
        const tab = this.tabs.find(t => t.id === this.activeTabId);
        if (tab) {
            tab.webview.reload();
        }
    }

    updateNavigationButtons() {
        const tab = this.tabs.find(t => t.id === this.activeTabId);
        if (tab) {
            try {
                this.backBtn.disabled = !tab.webview.canGoBack();
                this.forwardBtn.disabled = !tab.webview.canGoForward();
            } catch (e) {
                this.backBtn.disabled = true;
                this.forwardBtn.disabled = true;
            }
        } else {
            this.backBtn.disabled = true;
            this.forwardBtn.disabled = true;
        }
    }

    logout() {
        ipcRenderer.send('logout');
    }
}

// Initialize the browser when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    new NovaBrowser();
});
