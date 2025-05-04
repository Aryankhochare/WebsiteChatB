/**
 * Enhanced features for the RAG-Powered Website Chatbot
 * - Message history persistence
 * - UI improvements and animations
 * - Better error handling
 * - Image gallery functionality
 */

// Global variables for image handling
let currentCollection = null;
let currentPage = 1;
let imagesPerPage = 20;
let totalImages = 0;
let currentCategory = 'all';
let currentSort = 'newest';
let currentSearch = '';

document.addEventListener('DOMContentLoaded', () => {
    // Additional DOM Elements
    const searchWebsitesInput = document.createElement('input');
    searchWebsitesInput.type = 'text';
    searchWebsitesInput.placeholder = 'Search websites...';
    searchWebsitesInput.className = 'question-input';
    searchWebsitesInput.style.margin = '0.5rem';
    document.querySelector('.sidebar-header').appendChild(searchWebsitesInput);

    // Keyboard shortcuts
    document.addEventListener('keydown', (e) => {
        // Ctrl+K to focus search
        if (e.ctrlKey && e.key === 'k') {
            e.preventDefault();
            searchWebsitesInput.focus();
        }
        // Escape to close modal
        if (e.key === 'Escape' && addWebsiteModal.style.display === 'block') {
            addWebsiteModal.style.display = 'none';
        }
    });

    // Debounce function
    function debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }

    // Search websites functionality
    searchWebsitesInput.addEventListener('input', debounce(function() {
        const searchTerm = this.value.toLowerCase();
        const websites = document.querySelectorAll('.website-item');
        
        websites.forEach(website => {
            const title = website.querySelector('.website-title').textContent.toLowerCase();
            const info = website.querySelector('.website-info').textContent.toLowerCase();
            
            if (title.includes(searchTerm) || info.includes(searchTerm)) {
                website.style.display = 'block';
            } else {
                website.style.display = 'none';
            }
        });
    }, 300));

    // Chat history persistence
    function loadChatHistory() {
        const history = localStorage.getItem(`chat_history_${currentCollection}`);
        if (history) {
            chatMessages.innerHTML = history;
        } else {
            // Show welcome message for this collection
            chatMessages.innerHTML = `
                <div class="welcome-message">
                    <h2>Welcome to the ${currentCollection || 'Website'} Chat</h2>
                    <p>You can ask questions about the indexed website content. Try questions like:</p>
                    <ol>
                        <li>What is this website about?</li>
                        <li>Can you summarize the main content?</li>
                        <li>What services/products are offered?</li>
                    </ol>
                </div>
            `;
        }
        // Scroll to bottom
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    function saveChatHistory() {
        if (currentCollection) {
            localStorage.setItem(`chat_history_${currentCollection}`, chatMessages.innerHTML);
        }
    }

    // Enhanced collection select change handler
    const originalCollectionChangeHandler = collectionSelect.onchange;
    collectionSelect.addEventListener('change', () => {
        currentCollection = collectionSelect.value;
        
        if (currentCollection) {
            loadChatHistory();
            questionInput.disabled = false;
            sendBtn.disabled = false;
            
            // Update active website in sidebar
            const websiteItems = document.querySelectorAll('.website-item');
            websiteItems.forEach(item => {
                item.classList.remove('active');
                if (item.dataset.name === currentCollection) {
                    item.classList.add('active');
                }
            });
            
            // Load image gallery data when collection changes
            loadCollectionStats(currentCollection);
            loadCategories(currentCollection);
            loadImagesForCollection();
        } else {
            questionInput.disabled = true;
            sendBtn.disabled = true;
        }
    });

    // Improved typing effect for bot responses
    function typeMessage(element, text, index = 0) {
        if (index < text.length) {
            element.innerHTML += text.charAt(index);
            setTimeout(() => typeMessage(element, text, index + 1), 20);
        }
    }

    // Enhanced sendQuestion function with retry capability
    const originalSendQuestion = sendQuestion;
    window.sendQuestion = async function() {
        const question = questionInput.value.trim();
        
        if (!question || !currentCollection) {
            return;
        }
        
        // Display user message
        addMessageToChat('user', question);
        saveChatHistory();
        
        // Clear input
        questionInput.value = '';
        
        // Disable input and button while loading
        questionInput.disabled = true;
        sendBtn.disabled = true;
        
        // Show typing indicator
        const typingIndicator = addMessageToChat('bot', '<div class="typing-indicator"><span></span><span></span><span></span></div>', false);
        
        let retries = 2;
        
        async function tryQuery() {
            try {
                // Send question to API
                const response = await fetch('/api/query', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        query: question,
                        collection_name: currentCollection
                    })
                });
                
                if (!response.ok) {
                    throw new Error(`Server responded with ${response.status}`);
                }
                
                const data = await response.json();
                
                // Remove typing indicator
                typingIndicator.remove();
                
                // Display bot message
                const formattedAnswer = formatBotResponse(data.response);
                const botMessage = addMessageToChat('bot', formattedAnswer);
                
                // Save chat history
                saveChatHistory();
                
                // Re-enable input and button
                questionInput.disabled = false;
                sendBtn.disabled = false;
                questionInput.focus();
                
                // Highlight code blocks
                if (window.hljs) {
                    botMessage.querySelectorAll('pre code').forEach((block) => {
                        window.hljs.highlightBlock(block);
                    });
                }
                
            } catch (error) {
                console.error('Error getting response:', error);
                
                if (retries > 0) {
                    retries--;
                    console.log(`Retrying... ${retries} attempts remaining`);
                    await new Promise(resolve => setTimeout(resolve, 1000));
                    return tryQuery();
                }
                
                // Remove typing indicator
                typingIndicator.remove();
                
                // Display error message
                addMessageToChat('bot', `<p>Sorry, I encountered an error: ${error.message}</p><p>Please try again later.</p>`);
                saveChatHistory();
                
                // Re-enable input and button
                questionInput.disabled = false;
                sendBtn.disabled = false;
            }
        }
        
        tryQuery();
    };

    // Copy to clipboard functionality for code blocks
    chatMessages.addEventListener('click', (e) => {
        const codeBlock = e.target.closest('pre');
        if (codeBlock) {
            const code = codeBlock.textContent;
            navigator.clipboard.writeText(code).then(() => {
                // Show copied tooltip
                const tooltip = document.createElement('div');
                tooltip.textContent = 'Copied!';
                tooltip.style.position = 'absolute';
                tooltip.style.background = 'var(--primary-color)';
                tooltip.style.color = 'white';
                tooltip.style.padding = '5px 10px';
                tooltip.style.borderRadius = '3px';
                tooltip.style.fontSize = '12px';
                tooltip.style.top = `${e.clientY - 30}px`;
                tooltip.style.left = `${e.clientX}px`;
                tooltip.style.zIndex = '1000';
                
                document.body.appendChild(tooltip);
                
                setTimeout(() => {
                    tooltip.remove();
                }, 1500);
            });
        }
    });

    // Progress bar for indexing
    function createProgressBar() {
        const progressContainer = document.createElement('div');
        progressContainer.style.width = '100%';
        progressContainer.style.height = '4px';
        progressContainer.style.backgroundColor = 'var(--border-color)';
        progressContainer.style.marginTop = '10px';
        progressContainer.style.borderRadius = '2px';
        progressContainer.style.overflow = 'hidden';
        
        const progressBar = document.createElement('div');
        progressBar.style.width = '0%';
        progressBar.style.height = '100%';
        progressBar.style.backgroundColor = 'var(--primary-color)';
        progressBar.style.transition = 'width 0.3s ease';
        
        progressContainer.appendChild(progressBar);
        indexingStatus.appendChild(progressContainer);
        
        return progressBar;
    }

    // Auto-save draft question
    questionInput.addEventListener('input', debounce(function() {
        if (currentCollection && this.value.trim()) {
            localStorage.setItem(`draft_${currentCollection}`, this.value);
        }
    }, 500));

    // Load draft when selecting a collection
    const originalLoadCollections = loadCollections;
    window.loadCollections = async function() {
        await originalLoadCollections();
        
        // Load draft if exists
        if (currentCollection) {
            const draft = localStorage.getItem(`draft_${currentCollection}`);
            if (draft) {
                questionInput.value = draft;
            }
        }
    };

    // Check for new versions of the app
    const appVersion = '1.2.0'; // Updated version for image gallery feature
    const storedVersion = localStorage.getItem('app_version');
    
    if (storedVersion !== appVersion) {
        console.log(`Updating from ${storedVersion || 'new install'} to ${appVersion}`);
        // Show what's new notification
        const notification = document.createElement('div');
        notification.style.position = 'fixed';
        notification.style.bottom = '20px';
        notification.style.right = '20px';
        notification.style.backgroundColor = 'var(--primary-color)';
        notification.style.color = 'white';
        notification.style.padding = '10px 15px';
        notification.style.borderRadius = 'var(--border-radius)';
        notification.style.boxShadow = 'var(--shadow)';
        notification.style.zIndex = '1000';
        notification.style.maxWidth = '300px';
        notification.innerHTML = `
            <h4 style="margin-top: 0;">What's New in v${appVersion}</h4>
            <ul style="padding-left: 20px; margin-bottom: 10px;">
                <li>New image gallery feature</li>
                <li>Image categorization and search</li>
                <li>Dark mode support</li>
                <li>Improved message animations</li>
                <li>Search collections feature</li>
            </ul>
            <button id="close-notification" style="background: none; border: 1px solid white; color: white; padding: 5px 10px; border-radius: 4px; cursor: pointer; float: right;">Got it</button>
        `;
        
        document.body.appendChild(notification);
        
        document.getElementById('close-notification').addEventListener('click', () => {
            notification.remove();
            localStorage.setItem('app_version', appVersion);
        });
    }

    // Initialize image gallery
    initImageGallery();
});

/**
 * Load images for the currently selected collection
 */
async function loadImagesForCollection() {
    if (!currentCollection) return;
    
    const galleryDiv = document.getElementById('imageGallery');
    const loadingIndicator = document.getElementById('galleryLoadingIndicator');
    const errorMessageContainer = document.getElementById('errorMessageContainer');
    
    loadingIndicator.style.display = 'inline-block';
    errorMessageContainer.style.display = 'none'; // Hide any previous error
    
    try {
        let url = `/api/images/${currentCollection}?page=${currentPage}&limit=${imagesPerPage}&sort=${currentSort}`;
        
        if (currentSearch) {
            url += `&search=${encodeURIComponent(currentSearch)}`;
        }
        
        if (currentCategory !== 'all') {
            url += `&category=${encodeURIComponent(currentCategory)}`;
        }
        
        const response = await fetch(url);
        
        // Check if response is JSON
        const contentType = response.headers.get('content-type');
        if (!contentType || !contentType.includes('application/json')) {
            throw new Error('Server returned non-JSON response. The API endpoint might be incorrect or server is having issues.');
        }
        
        const result = await response.json();
        
        if (response.ok) {
            totalImages = result.count;
            
            if (result.images.length === 0) {
                let message = 'No images found in this collection';
                if (currentSearch) message += ` matching "${currentSearch}"`;
                if (currentCategory !== 'all') message += ` in category "${currentCategory}"`;
                
                galleryDiv.innerHTML = `
                    <div class="no-images">
                        <p>${message}</p>
                    </div>
                `;
                document.getElementById('galleryPagination').innerHTML = '';
            } else {
                let filterInfo = '';
                if (currentSearch) filterInfo += ` matching "${currentSearch}"`;
                if (currentCategory !== 'all') filterInfo += ` in category "${currentCategory}"`;
                
                galleryDiv.innerHTML = `
                    <p>Showing ${result.images.length} of ${result.count} images${filterInfo}</p>
                    <div class="image-grid" id="imageGrid"></div>
                `;
                
                const imageGrid = document.getElementById('imageGrid');
                
                result.images.forEach(image => {
                    const card = document.createElement('div');
                    card.className = 'image-card';
                    
                    const imageHTML = image.url
                        ? `<img src="${image.url}" alt="${image.alt || 'Image'}" loading="lazy">`
                        : `<div class="placeholder">Image not available</div>`;
                    
                    card.innerHTML = `
                        <div class="image-container">
                            ${imageHTML}
                        </div>
                        <div class="image-info">
                            <h5 class="card-title">${truncateText(image.alt || 'Image', 40)}</h5>
                            <p class="card-text small text-muted">${image.dimensions || 'Unknown dimensions'}</p>
                            <button class="btn btn-primary btn-action view-image-btn">
                                <i class="fas fa-search-plus"></i> View
                            </button>
                        </div>
                    `;
                    
                    // Add click event to view image in modal
                    card.querySelector('.view-image-btn').addEventListener('click', () => {
                        openImageModal(image);
                    });
                    
                    imageGrid.appendChild(card);
                });
                
                // Update pagination
                updatePagination(result.count);
            }
        } else {
            galleryDiv.innerHTML = `
                <div class="no-images">
                    <p>Error: ${result.detail || 'Failed to load images'}</p>
                </div>
            `;
        }
    } catch (error) {
        console.error('Error loading images:', error);
        errorMessageContainer.innerHTML = `Error: ${error.message}`;
        errorMessageContainer.style.display = 'block';
        galleryDiv.innerHTML = `
            <div class="no-images">
                <p>Could not load images. Please try again later.</p>
            </div>
        `;
    } finally {
        loadingIndicator.style.display = 'none';
    }
}

/**
 * Load image categories for a collection
 * @param {string} collectionName - The name of the collection
 */
async function loadCategories(collectionName) {
    try {
        const response = await fetch(`/image-categories/${collectionName}`);
        const categories = await response.json();
        
        const categoryFilters = document.querySelector('#categoryFilters');
        // Keep the "All" category
        categoryFilters.innerHTML = '<span class="badge bg-secondary category-badge active" data-category="all">All</span>';
        
        if (categories && categories.length > 0) {
            categories.forEach(category => {
                if (category) {  // Skip empty categories
                    const badge = document.createElement('span');
                    badge.className = 'badge bg-secondary category-badge';
                    badge.setAttribute('data-category', category);
                    badge.textContent = category;
                    badge.addEventListener('click', function() {
                        // Toggle active state
                        document.querySelectorAll('.category-badge').forEach(b => b.classList.remove('active'));
                        this.classList.add('active');
                        currentCategory = this.getAttribute('data-category');
                        currentPage = 1;
                        loadImagesForCollection();
                    });
                    categoryFilters.appendChild(badge);
                }
            });
        }
        
        // Add click handler to "All" category
        document.querySelector('.category-badge[data-category="all"]').addEventListener('click', function() {
            document.querySelectorAll('.category-badge').forEach(b => b.classList.remove('active'));
            this.classList.add('active');
            currentCategory = 'all';
            currentPage = 1;
            loadImagesForCollection();
        });
        
    } catch (error) {
        console.error('Error loading image categories:', error);
    }
}

/**
 * Load collection statistics
 * @param {string} collectionName - The name of the collection
 */
async function loadCollectionStats(collectionName) {
    try {
        const response = await fetch(`/collection-stats/${collectionName}`);
        const stats = await response.json();
        
        document.querySelector('#pagesCount').textContent = stats.pages_count || 0;
        document.querySelector('#imagesCount').textContent = stats.images_count || 0;
        document.querySelector('#contentSize').textContent = formatBytes(stats.content_size || 0);
        document.querySelector('#collectionStats').style.display = 'flex';
    } catch (error) {
        console.error('Error loading collection stats:', error);
        document.querySelector('#collectionStats').style.display = 'none';
    }
}

/**
 * Update pagination controls
 * @param {number} totalItems - Total number of items
 */
function updatePagination(totalItems) {
    const totalPages = Math.ceil(totalItems / imagesPerPage);
    const paginationElement = document.getElementById('galleryPagination');
    
    if (totalPages <= 1) {
        paginationElement.innerHTML = '';
        return;
    }
    
    let paginationHTML = '';
    
    // Previous button
    paginationHTML += `
        <li class="page-item ${currentPage === 1 ? 'disabled' : ''}">
            <a class="page-link" href="#" data-page="${currentPage - 1}" aria-label="Previous">
                <span aria-hidden="true">&laquo;</span>
            </a>
        </li>
    `;
    
    // Page numbers
    const maxVisiblePages = 5;
    let startPage = Math.max(1, currentPage - Math.floor(maxVisiblePages / 2));
    let endPage = Math.min(totalPages, startPage + maxVisiblePages - 1);
    
    if (endPage - startPage + 1 < maxVisiblePages) {
        startPage = Math.max(1, endPage - maxVisiblePages + 1);
    }
    
    if (startPage > 1) {
        paginationHTML += `
            <li class="page-item">
                <a class="page-link" href="#" data-page="1">1</a>
            </li>
        `;
        
        if (startPage > 2) {
            paginationHTML += `
                <li class="page-item disabled">
                    <a class="page-link" href="#">...</a>
                </li>
            `;
        }
    }
    
    for (let i = startPage; i <= endPage; i++) {
        paginationHTML += `
            <li class="page-item ${i === currentPage ? 'active' : ''}">
                <a class="page-link" href="#" data-page="${i}">${i}</a>
            </li>
        `;
    }
    
    if (endPage < totalPages) {
        if (endPage < totalPages - 1) {
            paginationHTML += `
                <li class="page-item disabled">
                    <a class="page-link" href="#">...</a>
                </li>
            `;
        }
        
        paginationHTML += `
            <li class="page-item">
                <a class="page-link" href="#" data-page="${totalPages}">${totalPages}</a>
            </li>
        `;
    }
    
    // Next button
    paginationHTML += `
        <li class="page-item ${currentPage === totalPages ? 'disabled' : ''}">
            <a class="page-link" href="#" data-page="${currentPage + 1}" aria-label="Next">
                <span aria-hidden="true">&raquo;</span>
            </a>
        </li>
    `;
    
    paginationElement.innerHTML = paginationHTML;
    
    // Add click handlers to pagination links
    document.querySelectorAll('.page-link').forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            const page = parseInt(this.getAttribute('data-page'));
            if (!isNaN(page) && page > 0 && page <= totalPages) {
                currentPage = page;
                loadImagesForCollection();
                // Scroll to top of gallery
                document.querySelector('.card-header').scrollIntoView({ behavior: 'smooth' });
            }
        });
    });
}

/**
 * Open image in modal
 * @param {Object} image - Image data
 */
function openImageModal(image) {
    const modal = new bootstrap.Modal(document.getElementById('imageModal'));
    const modalTitle = document.getElementById('imageModalLabel');
    const modalImageContainer = document.getElementById('modalImageContainer');
    const modalImageInfo = document.getElementById('modalImageInfo');
    const modalDownloadBtn = document.getElementById('modalDownloadBtn');
    const modalSourceBtn = document.getElementById('modalSourceBtn');
    
    modalTitle.textContent = image.alt || 'Image Preview';
    
    if (image.url) {
        modalImageContainer.innerHTML = `<img src="${image.url}" class="img-fluid" alt="${image.alt || 'Image'}">`;
        modalDownloadBtn.href = image.url;
        modalDownloadBtn.style.display = 'inline-block';
    } else {
        modalImageContainer.innerHTML = `<div class="placeholder p-5">Image not available</div>`;
        modalDownloadBtn.style.display = 'none';
    }
    
    let fileSize = image.file_size ? formatBytes(image.file_size) : 'Unknown';
    
    modalImageInfo.innerHTML = `
        <div class="row">
            <div class="col-md-4">
                <p><strong>Dimensions:</strong> ${image.dimensions || 'Unknown'}</p>
            </div>
            <div class="col-md-4">
                <p><strong>Size:</strong> ${fileSize}</p>
            </div>
            <div class="col-md-4">
                <p><strong>Source:</strong> ${image.page_url ? new URL(image.page_url).hostname : 'Unknown'}</p>
            </div>
        </div>
        <div class="row">
            <div class="col-12">
                <p><strong>Alt Text:</strong> ${image.alt || 'None'}</p>
            </div>
        </div>
        ${image.category ? `
        <div class="row">
            <div class="col-12">
                <p><strong>Category:</strong> ${image.category}</p>
            </div>
        </div>
        ` : ''}
    `;
    
    modalSourceBtn.href = image.page_url || '#';
    
    modal.show();
}

/**
 * Format bytes to human-readable format
 * @param {number} bytes - Bytes to format
 * @param {number} decimals - Number of decimal places
 * @returns {string} - Formatted string
 */
function formatBytes(bytes, decimals = 2) {
    if (bytes === 0) return '0 Bytes';
    
    const k = 1024;
    const dm = decimals < 0 ? 0 : decimals;
    const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
    
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    
    return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
}

/**
 * Truncate text with ellipsis
 * @param {string} text - Text to truncate
 * @param {number} maxLength - Maximum length
 * @returns {string} - Truncated text
 */
function truncateText(text, maxLength) {
    if (!text) return '';
    return text.length > maxLength ? text.substring(0, maxLength) + '...' : text;
}

/**
 * Initialize image gallery functionality
 */
function initImageGallery() {
    // Set up search button
    document.querySelector('#searchImagesBtn').addEventListener('click', function() {
        currentSearch = document.querySelector('#imageSearch').value;
        currentPage = 1;
        if (currentCollection) {
            loadImagesForCollection();
        }
    });
    
    // Enter key for search
    document.querySelector('#imageSearch').addEventListener('keyup', function(event) {
        if (event.key === 'Enter') {
            document.querySelector('#searchImagesBtn').click();
        }
    });
    
    // Set up sort change listener
    document.querySelector('#sortOrder').addEventListener('change', function() {
        currentSort = this.value;
        if (currentCollection) {
            loadImagesForCollection();
        }
    });
    
    // Try to get collection from URL parameter
    const urlParams = new URLSearchParams(window.location.search);
    const collectionParam = urlParams.get('collection');
    
    if (collectionParam) {
        const collectionSelect = document.querySelector('#collectionSelect');
        for (let i = 0; i < collectionSelect.options.length; i++) {
            if (collectionSelect.options[i].value === collectionParam) {
                collectionSelect.selectedIndex = i;
                currentCollection = collectionParam;
                loadCollectionStats(currentCollection);
                loadCategories(currentCollection);
                loadImagesForCollection();
                break;
            }
        }
    }
}

/**
 * Load indexed collections for the dropdown
 */
async function loadCollections() {
    try {
        const response = await fetch('/collections');
        const collections = await response.json();
        
        const collectionSelect = document.getElementById('collectionSelect');
        // Clear existing options
        collectionSelect.innerHTML = '<option value="">Select a website collection</option>';
        
        if (collections.length === 0) {
            const option = document.createElement('option');
            option.text = 'No collections available';
            option.disabled = true;
            collectionSelect.add(option);
        } else {
            collections.forEach(collection => {
                const option = document.createElement('option');
                option.value = collection;
                option.text = collection;
                collectionSelect.add(option);
            });
        }
    } catch (error) {
        console.error('Error loading collections:', error);
    }
}