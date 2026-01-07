/**
 * D&D Combat Engine - Performance Manager
 * Client-side optimization utilities.
 */

/**
 * Performance Manager - Utilities for optimizing rendering and API calls
 */
class PerformanceManager {
    constructor() {
        // API response cache
        this.apiCache = new Map();
        this.cacheMaxAge = 60000; // 1 minute default

        // Pending batch requests
        this.batchQueue = [];
        this.batchTimeout = null;
        this.batchDelay = 50; // ms to wait before sending batch

        // RAF (requestAnimationFrame) state
        this.rafCallbacks = new Map();
        this.rafId = null;

        // Memory monitoring
        this.memoryWarningThreshold = 100 * 1024 * 1024; // 100MB

        // Performance metrics
        this.metrics = {
            apiCalls: 0,
            cacheHits: 0,
            batchedRequests: 0,
            renderFrames: 0,
            lastFrameTime: 0
        };

        this.init();
    }

    init() {
        // Start RAF loop if needed
        this.startRAFLoop();

        // Monitor memory periodically
        if (performance.memory) {
            setInterval(() => this.checkMemory(), 30000);
        }
    }

    // ==================== Render Optimization ====================

    /**
     * Throttle a function to run at most once per frame
     * @param {string} key - Unique identifier for this throttled function
     * @param {Function} fn - Function to throttle
     */
    throttleRender(key, fn) {
        this.rafCallbacks.set(key, fn);
    }

    /**
     * Debounce a function
     * @param {Function} fn - Function to debounce
     * @param {number} delay - Delay in ms
     */
    debounce(fn, delay = 100) {
        let timeoutId = null;
        return (...args) => {
            clearTimeout(timeoutId);
            timeoutId = setTimeout(() => fn(...args), delay);
        };
    }

    /**
     * Throttle a function to run at most once per interval
     * @param {Function} fn - Function to throttle
     * @param {number} limit - Minimum interval in ms
     */
    throttle(fn, limit = 16) {
        let lastRun = 0;
        let timeout = null;

        return (...args) => {
            const now = Date.now();

            if (now - lastRun >= limit) {
                lastRun = now;
                fn(...args);
            } else {
                clearTimeout(timeout);
                timeout = setTimeout(() => {
                    lastRun = Date.now();
                    fn(...args);
                }, limit - (now - lastRun));
            }
        };
    }

    /**
     * Request animation frame with tracking
     * @param {Function} callback - Frame callback
     */
    requestFrame(callback) {
        return requestAnimationFrame((timestamp) => {
            this.metrics.renderFrames++;
            this.metrics.lastFrameTime = timestamp;
            callback(timestamp);
        });
    }

    /**
     * Start the RAF loop for throttled renders
     */
    startRAFLoop() {
        const loop = () => {
            // Execute all queued render callbacks
            for (const [key, fn] of this.rafCallbacks) {
                try {
                    fn();
                } catch (e) {
                    console.error(`[Performance] RAF callback error (${key}):`, e);
                }
            }
            this.rafCallbacks.clear();

            this.rafId = requestAnimationFrame(loop);
        };

        this.rafId = requestAnimationFrame(loop);
    }

    /**
     * Stop the RAF loop
     */
    stopRAFLoop() {
        if (this.rafId) {
            cancelAnimationFrame(this.rafId);
            this.rafId = null;
        }
    }

    // ==================== API Caching ====================

    /**
     * Cache an API response
     * @param {string} key - Cache key (usually URL + params)
     * @param {any} data - Response data
     * @param {number} maxAge - Max age in ms
     */
    cacheResponse(key, data, maxAge = this.cacheMaxAge) {
        this.apiCache.set(key, {
            data,
            timestamp: Date.now(),
            maxAge
        });
    }

    /**
     * Get cached API response
     * @param {string} key - Cache key
     * @returns {any|null} Cached data or null if expired/missing
     */
    getCachedResponse(key) {
        const entry = this.apiCache.get(key);

        if (!entry) {
            return null;
        }

        // Check if expired
        if (Date.now() - entry.timestamp > entry.maxAge) {
            this.apiCache.delete(key);
            return null;
        }

        this.metrics.cacheHits++;
        return entry.data;
    }

    /**
     * Invalidate cached responses matching a pattern
     * @param {string} pattern - Pattern to match (prefix)
     */
    invalidateCache(pattern) {
        for (const key of this.apiCache.keys()) {
            if (key.startsWith(pattern)) {
                this.apiCache.delete(key);
            }
        }
    }

    /**
     * Clear entire API cache
     */
    clearCache() {
        this.apiCache.clear();
    }

    // ==================== Request Batching ====================

    /**
     * Add a request to the batch queue
     * @param {Object} request - Request configuration
     * @returns {Promise} Promise that resolves with the response
     */
    batchRequest(request) {
        return new Promise((resolve, reject) => {
            this.batchQueue.push({ request, resolve, reject });

            // Start batch timer if not already running
            if (!this.batchTimeout) {
                this.batchTimeout = setTimeout(() => {
                    this.flushBatch();
                }, this.batchDelay);
            }
        });
    }

    /**
     * Flush the batch queue
     */
    async flushBatch() {
        this.batchTimeout = null;

        if (this.batchQueue.length === 0) return;

        const batch = [...this.batchQueue];
        this.batchQueue = [];

        this.metrics.batchedRequests += batch.length;

        // Group requests by endpoint
        const groups = new Map();
        for (const item of batch) {
            const key = item.request.endpoint;
            if (!groups.has(key)) {
                groups.set(key, []);
            }
            groups.get(key).push(item);
        }

        // Process each group
        for (const [endpoint, items] of groups) {
            // If all requests to same endpoint, send as batch
            if (items.length > 1 && items[0].request.batchable) {
                try {
                    const response = await this.sendBatchedRequest(endpoint, items);
                    // Distribute responses to waiting promises
                    items.forEach((item, index) => {
                        item.resolve(response[index]);
                    });
                } catch (error) {
                    items.forEach(item => item.reject(error));
                }
            } else {
                // Send individually
                for (const item of items) {
                    try {
                        const response = await this.sendSingleRequest(item.request);
                        item.resolve(response);
                    } catch (error) {
                        item.reject(error);
                    }
                }
            }
        }
    }

    /**
     * Send a batched request
     */
    async sendBatchedRequest(endpoint, items) {
        // This would be implemented based on your API's batch endpoint
        // For now, just send individually
        const results = [];
        for (const item of items) {
            results.push(await this.sendSingleRequest(item.request));
        }
        return results;
    }

    /**
     * Send a single request
     */
    async sendSingleRequest(request) {
        this.metrics.apiCalls++;

        const response = await fetch(request.url, {
            method: request.method || 'GET',
            headers: request.headers || { 'Content-Type': 'application/json' },
            body: request.body ? JSON.stringify(request.body) : undefined
        });

        return response.json();
    }

    // ==================== Memory Management ====================

    /**
     * Check memory usage and warn if high
     */
    checkMemory() {
        if (!performance.memory) return;

        const used = performance.memory.usedJSHeapSize;
        const total = performance.memory.jsHeapSizeLimit;

        if (used > this.memoryWarningThreshold) {
            console.warn(`[Performance] High memory usage: ${(used / 1024 / 1024).toFixed(1)}MB`);

            // Attempt cleanup
            this.cleanupUnusedAssets();
        }
    }

    /**
     * Clean up unused assets
     */
    cleanupUnusedAssets() {
        // Clear old cache entries
        const now = Date.now();
        for (const [key, entry] of this.apiCache) {
            if (now - entry.timestamp > entry.maxAge) {
                this.apiCache.delete(key);
            }
        }

        // Suggest garbage collection (hint to browser)
        if (window.gc) {
            window.gc();
        }

        console.log('[Performance] Cleaned up unused assets');
    }

    // ==================== Virtual List ====================

    /**
     * Create a virtual list for long lists (only render visible items)
     * @param {Array} items - All items
     * @param {Object} options - Virtual list options
     */
    createVirtualList(items, options = {}) {
        const {
            itemHeight = 40,
            containerHeight = 400,
            overscan = 5
        } = options;

        const visibleCount = Math.ceil(containerHeight / itemHeight) + overscan * 2;

        return {
            items,
            itemHeight,
            containerHeight,
            totalHeight: items.length * itemHeight,

            getVisibleRange(scrollTop) {
                const startIndex = Math.max(0, Math.floor(scrollTop / itemHeight) - overscan);
                const endIndex = Math.min(items.length, startIndex + visibleCount);

                return {
                    startIndex,
                    endIndex,
                    offsetY: startIndex * itemHeight,
                    visibleItems: items.slice(startIndex, endIndex)
                };
            }
        };
    }

    // ==================== Image Optimization ====================

    /**
     * Lazy load an image
     * @param {HTMLImageElement} img - Image element
     * @param {string} src - Image source
     */
    lazyLoadImage(img, src) {
        if ('loading' in HTMLImageElement.prototype) {
            // Native lazy loading
            img.loading = 'lazy';
            img.src = src;
        } else {
            // Intersection Observer fallback
            const observer = new IntersectionObserver((entries) => {
                entries.forEach(entry => {
                    if (entry.isIntersecting) {
                        img.src = src;
                        observer.unobserve(img);
                    }
                });
            });
            observer.observe(img);
        }
    }

    /**
     * Preload images
     * @param {string[]} urls - Image URLs to preload
     */
    preloadImages(urls) {
        return Promise.all(urls.map(url => {
            return new Promise((resolve, reject) => {
                const img = new Image();
                img.onload = resolve;
                img.onerror = reject;
                img.src = url;
            });
        }));
    }

    // ==================== Metrics ====================

    /**
     * Get performance metrics
     */
    getMetrics() {
        const hitRate = this.metrics.apiCalls > 0
            ? (this.metrics.cacheHits / this.metrics.apiCalls * 100).toFixed(1)
            : 0;

        return {
            ...this.metrics,
            cacheHitRate: `${hitRate}%`,
            cacheSize: this.apiCache.size,
            memoryUsed: performance.memory
                ? `${(performance.memory.usedJSHeapSize / 1024 / 1024).toFixed(1)}MB`
                : 'N/A'
        };
    }

    /**
     * Reset metrics
     */
    resetMetrics() {
        this.metrics = {
            apiCalls: 0,
            cacheHits: 0,
            batchedRequests: 0,
            renderFrames: 0,
            lastFrameTime: 0
        };
    }

    // ==================== Frame Rate Monitor ====================

    /**
     * Monitor frame rate
     * @param {Function} callback - Called with FPS value
     * @param {number} sampleRate - How often to report (ms)
     */
    monitorFPS(callback, sampleRate = 1000) {
        let frameCount = 0;
        let lastTime = performance.now();

        const countFrame = () => {
            frameCount++;
            requestAnimationFrame(countFrame);
        };

        requestAnimationFrame(countFrame);

        return setInterval(() => {
            const now = performance.now();
            const elapsed = now - lastTime;
            const fps = Math.round(frameCount / (elapsed / 1000));

            callback(fps);

            frameCount = 0;
            lastTime = now;
        }, sampleRate);
    }
}

// Export singleton
export const performanceManager = new PerformanceManager();
export default performanceManager;
