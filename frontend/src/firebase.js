// frontend/src/firebase.js
import { initializeApp } from "firebase/app";
import { getAuth, GoogleAuthProvider, signInWithPopup } from "firebase/auth";

// TODO: Replace this with your actual Firebase config from the Firebase Console
// Go to: https://console.firebase.google.com/
// Select project: tempraai-b079e
// Project Settings → Your apps → Add web app (if needed)
// Copy the config object from "Firebase SDK snippet" → "Config"

const firebaseConfig = {
  apiKey: "AIzaSyAMCNv35sUIgjGxR7blmFevDmuARoQzllM",
  authDomain: "tempraai-67830.firebaseapp.com",
  projectId: "tempraai-67830",
  storageBucket: "tempraai-67830.firebasestorage.app",
  messagingSenderId: "773380294958",
  appId: "1:773380294958:web:b2983e0e9f4708b0f792bf",
  measurementId: "G-07BTPQ81XG"
};


const app = initializeApp(firebaseConfig);
const auth = getAuth(app);
// const analytics = getAnalytics(app);

export { auth, GoogleAuthProvider, signInWithPopup }; 