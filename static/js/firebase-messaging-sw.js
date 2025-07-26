// This script runs in the background
// Give the service worker access to Firebase Messaging.
importScripts('https://www.gstatic.com/firebasejs/9.23.0/firebase-app-compat.js');
importScripts('https://www.gstatic.com/firebasejs/9.23.0/firebase-messaging-compat.js');

// Initialize the Firebase app in the service worker with your project's configuration
const firebaseConfig = {
    apiKey: "AIzaSyAcxHbkWZTOm0hRQiwtB-tqQUoVvkEVUMM",
    authDomain: "nasser-8ed51.firebaseapp.com",
    projectId: "nasser-8ed51",
    storageBucket: "nasser-8ed51.firebasestorage.app",
    messagingSenderId: "452598851",
    appId: "1:452598798851:web:30124252bdf0569e6e8c36",
    measurementId: "G-P21WT74CNN"
};

firebase.initializeApp(firebaseConfig);

// Retrieve an instance of Firebase Messaging so that it can handle background messages.
const messaging = firebase.messaging();

messaging.onBackgroundMessage((payload) => {
    console.log('[firebase-messaging-sw.js] Received background message ', payload);
    
    // Customize the notification here
    const notificationTitle = payload.notification.title;
    const notificationOptions = {
        body: payload.notification.body,
        icon: payload.notification.image || '/static/images/default-notification-icon.png' // A default icon
    };

    self.registration.showNotification(notificationTitle, notificationOptions);
}); 