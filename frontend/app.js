// app.js

// 後端 API base URL
// 開發時請設定為你的 Flask 後端服務位址
const API_BASE = "http://localhost:5000";

// --- 通用工具函數 ---

/**
 * 顯示訊息給使用者。
 * 訊息內容會使用 textContent 插入，防止 XSS。
 * @param {string} message 訊息內容。
 * @param {'success'|'error'|'info'} type 訊息類型。
 * @param {HTMLElement} targetElement 顯示訊息的 DOM 元素。
 */
function showMessage(message, type, targetElement) {
    if (!targetElement) return;

    // 清除所有可能的訊息類別
    targetElement.className = '';
    targetElement.textContent = ''; // *** 資安要求：使用 textContent 防止 XSS ***

    if (message) {
        targetElement.textContent = message;
        targetElement.classList.add(`${type}-message`);
        // 訊息顯示一段時間後自動消失
        setTimeout(() => {
            targetElement.textContent = '';
            targetElement.className = '';
        }, 5000);
    }
}

/**
 * 封裝 fetch 請求，自動帶入 credentials: "include" 並處理通用錯誤。
 * 錯誤訊息會被處理成通用文字，不顯示後端細節。
 * @param {string} url 請求的 URL。
 * @param {object} options fetch 請求的選項。
 * @returns {Promise<Response>} fetch 回傳的 Response 物件。
 * @throws {Error} 如果請求失敗或伺服器回傳非 2xx 狀態碼。
 */
async function secureFetch(url, options = {}) {
    try {
        const response = await fetch(url, {
            ...options,
            credentials: "include", // *** 資安要求：確保跨來源請求帶上 cookie (Flask session) ***
        });

        if (!response.ok) {
            // 嘗試解析錯誤訊息，但只顯示通用訊息，避免洩露後端細節
            let errorDetail = 'An unknown error occurred.';
            try {
                const errorData = await response.json();
                // 避免顯示後端堆疊或內部細節，只取特定字段或使用通用訊息
                errorDetail = errorData.message || errorData.error || `Server responded with status ${response.status}.`;
            } catch (e) {
                // 如果無法解析 JSON，則使用通用訊息
                errorDetail = `Server responded with status ${response.status}.`;
            }
            // 拋出錯誤，讓調用者處理顯示
            throw new Error(errorDetail);
        }
        return response;
    } catch (error) {
        console.error("Fetch error:", error);
        // *** 資安要求：錯誤訊息使用通用文字，不顯示後端的堆疊或內部細節 ***
        throw new Error(`Network error or server unavailable. Please try again. (${error.message})`);
    }
}


// --- 登入頁 (index.html) 邏輯 ---
// 判斷當前頁面是否為 index.html
if (window.location.pathname.endsWith('index.html') || window.location.pathname === '/') {
    const loginForm = document.getElementById('loginForm');
    const messageElement = document.getElementById('message');

    if (loginForm) {
        loginForm.addEventListener('submit', async (event) => {
            event.preventDefault(); // 阻止表單預設提交行為

            const username = document.getElementById('username').value;
            const password = document.getElementById('password').value;

            showMessage('', 'info', messageElement); // 清除舊訊息

            try {
                const response = await secureFetch(`${API_BASE}/login`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ username, password }),
                });

                if (response.ok) {
                    // 登入成功，導向商品頁
                    window.location.href = 'products.html';
                } else {
                    // 登入失敗，顯示通用錯誤訊息
                    showMessage('Login failed. Please check your credentials.', 'error', messageElement);
                }
            } catch (error) {
                // 網路錯誤或伺服器無回應等情況，顯示通用錯誤訊息
                showMessage('Login failed. Please try again later.', 'error', messageElement);
            }
        });
    }
}


// --- 商品頁 (products.html) 邏輯 ---
// 判斷當前頁面是否為 products.html
if (window.location.pathname.endsWith('products.html')) {
    const productListElement = document.getElementById('productList');
    const searchForm = document.getElementById('searchForm');
    const addProductForm = document.getElementById('addProductForm');
    const messageElement = document.getElementById('message');
    const logoutButton = document.getElementById('logoutButton');
    const clearSearchButton = document.getElementById('clearSearchButton');

    /**
     * 顯示商品列表。
     * 確保所有後端回傳的資料都使用 textContent 插入，防止 XSS。
     * @param {Array<Object>} products 商品資料陣列。
     */
    function displayProducts(products) {
        productListElement.textContent = ''; // 清空現有列表，*** 資安要求：清空時也避免 innerHTML ***

        if (products.length === 0) {
            const noProductsMessage = document.createElement('p');
            noProductsMessage.textContent = 'No products found.'; // *** 資安要求：使用 textContent ***
            productListElement.appendChild(noProductsMessage);
            return;
        }

        products.forEach(product => {
            const productItem = document.createElement('div');
            productItem.classList.add('product-item');

            const name = document.createElement('h3');
            name.textContent = product.name; // *** 資安要求：使用 textContent 防止 XSS ***

            const description = document.createElement('p');
            description.textContent = product.description; // *** 資安要求：使用 textContent 防止 XSS ***

            const price = document.createElement('p');
            price.classList.add('price');
            price.textContent = `Price: $${parseFloat(product.price).toFixed(2)}`; // *** 資安要求：使用 textContent ***

            const stock = document.createElement('p');
            stock.classList.add('stock');
            stock.textContent = `Stock: ${product.stock}`; // *** 資安要求：使用 textContent ***

            productItem.appendChild(name);
            productItem.appendChild(description);
            productItem.appendChild(price);
            productItem.appendChild(stock);

            productListElement.appendChild(productItem);
        });
    }

    /**
     * 取得並顯示所有商品或搜尋結果。
     * @param {string} query 搜尋關鍵字 (可選)。
     */
    async function fetchAndDisplayProducts(query = '') {
        showMessage('Loading products...', 'info', messageElement);
        productListElement.textContent = 'Loading products...'; // 顯示載入中訊息，*** 資安要求：使用 textContent ***

        let url = `${API_BASE}/products`;
        if (query) {
            url = `${API_BASE}/products/search?q=${encodeURIComponent(query)}`;
        }

        try {
            const response = await secureFetch(url);
            const products = await response.json();
            displayProducts(products);
            showMessage('', 'info', messageElement); // 清除載入訊息
        } catch (error) {
            console.error("Failed to fetch products:", error);
            productListElement.textContent = 'Failed to load products. Please try again.'; // *** 資安要求：使用 textContent ***
            showMessage('Failed to load products. Please try again later.', 'error', messageElement);
        }
    }

    // 頁面載入時自動載入商品
    document.addEventListener('DOMContentLoaded', () => {
        fetchAndDisplayProducts();
    });

    // 搜尋表單提交事件
    if (searchForm) {
        searchForm.addEventListener('submit', async (event) => {
            event.preventDefault();
            const searchQuery = document.getElementById('searchQuery').value;
            fetchAndDisplayProducts(searchQuery);
        });
    }

    // 清除搜尋按鈕事件
    if (clearSearchButton) {
        clearSearchButton.addEventListener('click', () => {
            document.getElementById('searchQuery').value = ''; // 清空搜尋框
            fetchAndDisplayProducts(); // 重新載入所有商品
        });
    }

    // 新增商品表單提交事件
    if (addProductForm) {
        addProductForm.addEventListener('submit', async (event) => {
            event.preventDefault();

            const name = document.getElementById('productName').value;
            const description = document.getElementById('productDescription').value;
            const price = parseFloat(document.getElementById('productPrice').value);
            const stock = parseInt(document.getElementById('productStock').value, 10);

            // 基本輸入驗證
            if (!name || isNaN(price) || price < 0 || isNaN(stock) || stock < 0) {
                showMessage('Please fill in all product fields correctly.', 'error', messageElement);
                return;
            }

            showMessage('Adding product...', 'info', messageElement);

            try {
                const response = await secureFetch(`${API_BASE}/products`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ name, description, price, stock }),
                });

                if (response.ok) {
                    showMessage('Product added successfully!', 'success', messageElement);
                    addProductForm.reset(); // 清空表單
                    fetchAndDisplayProducts(); // 重新載入商品列表以顯示新商品
                } else {
                    // 伺服器回傳非 2xx 狀態碼，例如 401 未授權
                    showMessage('Failed to add product. You might not be authorized or input is invalid.', 'error', messageElement);
                }
            } catch (error) {
                // 網路錯誤或伺服器無回應等情況，顯示通用錯誤訊息
                showMessage('Failed to add product. Please try again later.', 'error', messageElement);
            }
        });
    }

    // 登出按鈕事件
    if (logoutButton) {
        logoutButton.addEventListener('click', () => {
            // 由於 Flask session 是伺服器端管理，前端登出通常是清除客戶端狀態並導向登入頁。
            // 如果後端有提供 /logout 端點來清除伺服器端 session，則應呼叫該端點。
            // 在此範例中，我們假設導向登入頁即可，讓伺服器端 session 自然過期。
            // 如果需要明確清除伺服器端 session，則需要一個 POST /logout 端點。
            // 為了簡潔，這裡只做前端導向。
            window.location.href = 'index.html';
        });
    }
}
