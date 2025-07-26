document.addEventListener('DOMContentLoaded', function () {

    // Helper function to get CSRF token
    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }
    const csrftoken = getCookie('csrftoken');
    const userIsAuthenticated = document.body.dataset.user === 'true';

    // --- Navbar scroll effect ---
    const navbar = document.getElementById('main-navbar');
    if (navbar) {
        window.addEventListener('scroll', function() {
            if (window.scrollY > 50) {
                navbar.classList.add('scrolled');
            } else {
                navbar.classList.remove('scrolled');
            }
        });
    }
    
    // --- Event Delegation for Product Card actions ---
    document.body.addEventListener('click', function(e) {
        
        // Add to Cart Button
        const cartBtn = e.target.closest('.add-to-cart-btn-alt');
        if (cartBtn) {
            e.preventDefault();
            const productId = cartBtn.dataset.product;
            const action = cartBtn.dataset.action;
            
            if (userIsAuthenticated) {
                updateUserOrder(productId, action);
            } else {
                window.location.href = '/login/'; 
            }
            return; // Stop further execution
        }

        // Quick View Button
        const quickViewBtn = e.target.closest('.quick-view-btn');
        if (quickViewBtn) {
            e.preventDefault();
            const productId = quickViewBtn.dataset.productId;
            openQuickViewModal(productId);
            return; // Stop further execution
        }
    });

    // --- Unified function to update cart ---
    function updateUserOrder(productId, action) {
        const url = '/add_to_cart/';
        fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrftoken,
            },
            body: JSON.stringify({ 'productId': productId, 'action': action })
        })
        .then(response => response.json())
        .then(data => {
            console.log('Cart updated:', data);
            // Optionally, show a success message or update cart icon
            location.reload(); // Simple reload to show updated cart state
        })
        .catch(error => {
            console.error('Error updating cart:', error);
        });
    }

    // --- Quick View Modal ---
    const quickViewModal = new bootstrap.Modal(document.getElementById('quickViewModal'));
    
    function openQuickViewModal(productId) {
        const url = `/quick-view/${productId}/`;
        const modalBody = document.getElementById('quickViewModalBody');
        
        // Show loading spinner
        modalBody.innerHTML = '<div class="d-flex justify-content-center p-5"><div class="spinner-border" role="status"><span class="visually-hidden">Loading...</span></div></div>';
        quickViewModal.show();

        fetch(url)
            .then(response => response.json())
            .then(data => {
                modalBody.innerHTML = `
                    <div class="row">
                        <div class="col-md-5">
                            <img src="${data.image_url}" class="img-fluid rounded" alt="${data.name}">
                        </div>
                        <div class="col-md-7">
                            <h3>${data.name}</h3>
                            <p class="text-muted">${data.description || ''}</p>
                            <h4 class="text-primary fw-bold my-3">${data.price} جنيه</h4>
                            <a href="${data.product_url}" class="btn btn-primary">عرض التفاصيل الكاملة</a>
                        </div>
                    </div>
                `;
            })
            .catch(error => {
                console.error('Error fetching quick view data:', error);
                modalBody.innerHTML = '<p class="text-danger">حدث خطأ أثناء تحميل البيانات.</p>';
            });
    }

    // FAQ Accordion
    const faqItems = document.querySelectorAll('.faq-item');
    faqItems.forEach(item => {
        const question = item.querySelector('.faq-question');
        question.addEventListener('click', () => {
            const answer = item.querySelector('.faq-answer');
            const icon = question.querySelector('i');

            const isOpen = item.classList.contains('open');

            // Close all other items
            faqItems.forEach(otherItem => {
                otherItem.classList.remove('open');
                otherItem.querySelector('.faq-answer').style.maxHeight = null;
                otherItem.querySelector('.faq-question i').classList.remove('fa-chevron-up');
                otherItem.querySelector('.faq-question i').classList.add('fa-chevron-down');
            });

            // Open the clicked item if it was closed
            if (!isOpen) {
                item.classList.add('open');
                answer.style.maxHeight = answer.scrollHeight + 'px';
                icon.classList.remove('fa-chevron-down');
                icon.classList.add('fa-chevron-up');
            }
        });
    });

    // Scroll Animation
    const sections = document.querySelectorAll('.content-section');
    const observer = new IntersectionObserver(entries => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('is-visible');
            }
        });
    }, {
        threshold: 0.1
    });

    sections.forEach(section => {
        section.classList.add('fade-in-section');
        observer.observe(section);
    });

    // --- Firebase Social Authentication ---
    let isPopupOpen = false; // Flag to prevent multiple popups

    function handleSocialLogin(provider) {
        if (isPopupOpen) {
            console.warn("Authentication popup is already open.");
            return;
        }
        isPopupOpen = true;

        auth.signInWithPopup(provider)
            .then((result) => {
                isPopupOpen = false;
                const user = result.user;
                user.getIdToken().then((idToken) => {
                    sendTokenToServer(idToken);
                });
            }).catch((error) => {
                isPopupOpen = false;
                // Don't show an error alert if the user intentionally closes the popup.
                if (error.code !== 'auth/popup-closed-by-user' && error.code !== 'auth/cancelled-popup-request') {
                    console.error("Social login error:", error.message);
                    alert("حدث خطأ أثناء تسجيل الدخول. يرجى المحاولة مرة أخرى.");
                } else {
                    console.log("Popup closed or cancelled by user.");
                }
            });
    }

    function sendTokenToServer(idToken) {
        const url = '/social-login/'; // This will be our new Django endpoint
        fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrftoken,
            },
            body: JSON.stringify({ 'id_token': idToken })
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                window.location.href = '/'; // Redirect to home on successful login
            } else {
                const errorMessage = data.message || 'فشل التحقق من الخادم.';
                console.error('Server verification failed:', errorMessage);
                alert(errorMessage);
            }
        })
        .catch(error => {
            console.error('Server communication failed:', error);
            alert('حدث خطأ أثناء الاتصال بالخادم.');
        });
    }

    // Google Login
    const googleLoginBtn = document.getElementById('google-login-btn');
    const googleRegisterBtn = document.getElementById('google-register-btn');
    if (googleLoginBtn) {
        googleLoginBtn.addEventListener('click', () => {
            const provider = new firebase.auth.GoogleAuthProvider();
            handleSocialLogin(provider);
        });
    }
     if (googleRegisterBtn) {
        googleRegisterBtn.addEventListener('click', () => {
            const provider = new firebase.auth.GoogleAuthProvider();
            handleSocialLogin(provider);
        });
    }


    // Facebook Login
    const facebookLoginBtn = document.getElementById('facebook-login-btn');
    const facebookRegisterBtn = document.getElementById('facebook-register-btn');

    if (facebookLoginBtn) {
        facebookLoginBtn.addEventListener('click', () => {
            const provider = new firebase.auth.FacebookAuthProvider();
            handleSocialLogin(provider);
        });
    }
    if(facebookRegisterBtn){
         facebookRegisterBtn.addEventListener('click', () => {
            const provider = new firebase.auth.FacebookAuthProvider();
            handleSocialLogin(provider);
        });
    }

    // --- Address Delete Confirmation ---
    document.body.addEventListener('submit', function(e) {
        if (e.target.matches('.delete-address-form')) {
            const form = e.target;
            const confirmBtn = form.querySelector('button[type="submit"]');
            const message = confirmBtn.dataset.confirmMessage || 'Are you sure you want to delete this?';
            if (!confirm(message)) {
                e.preventDefault();
            }
        }
    });

    // --- Payment Method Delete Confirmation ---
    document.body.addEventListener('submit', function(e) {
        if (e.target.matches('.delete-payment-form')) {
            const form = e.target;
            const confirmBtn = form.querySelector('button[type="submit"]');
            const message = confirmBtn.dataset.confirmMessage || 'Are you sure you want to delete this payment method?';
            if (!confirm(message)) {
                e.preventDefault();
            }
        }
    });

    // Push Notification Logic
    function initializeFirebaseMessaging() {
        const messaging = firebase.messaging();

        // Handle incoming messages. Called when:
        // - Web app is running in foreground
        messaging.onMessage((payload) => {
            console.log('Message received. ', payload);
            // Here you can show a custom in-app notification
            // For example, using a library like Noty.js or just a simple div
            alert(`Notification: ${payload.notification.title}`);
        });
    }

    function requestNotificationPermission() {
        console.log('Requesting notification permission...');
        const messaging = firebase.messaging();
        
        Notification.requestPermission().then((permission) => {
            if (permission === 'granted') {
                console.log('Notification permission granted.');
                // Get the token
                return messaging.getToken({ vapidKey: 'BFlPZWTZJg3G_Kq6nLNNWz2f-5P_cZJbB-y-sJ_gA-1uI_wB-tZ_3E_vC-7bA_fB_9gJ_jH-kK_lA' });
            } else {
                console.log('Unable to get permission to notify.');
                throw new Error('Notification permission not granted');
            }
        }).then(token => {
            console.log('FCM Token:', token);
            // Send this token to your server
            sendTokenToServer(token);
        }).catch((err) => {
            console.log('An error occurred while retrieving token. ', err);
        });
    }

    function sendTokenToServer(token) {
        // We need the CSRF token for the POST request
        const csrftoken = getCookie('csrftoken'); 
        
        fetch('/subscribe-push/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrftoken
            },
            body: JSON.stringify({ token: token })
        })
        .then(response => response.json())
        .then(data => {
            console.log('Token sent to server:', data);
            if(data.status === 'success') {
                alert('Subscribed to notifications successfully!');
                // Update UI
                document.getElementById('subscribeBtn').style.display = 'none';
                document.getElementById('unsubscribeBtn').style.display = 'inline-block';
            }
        })
        .catch(error => {
            console.error('Error sending token to server:', error);
        });
    }

    // Initialize Firebase messaging when the script loads
    if (firebase) {
        initializeFirebaseMessaging();
    }
});