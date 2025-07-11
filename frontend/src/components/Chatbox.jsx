import React, { useState, useRef, useEffect } from "react";
import { ArrowUp } from 'lucide-react';

const Chatbox = () => {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [pendingChanges, setPendingChanges] = useState(null);
  const [currentIntent, setCurrentIntent] = useState(null);
  const [showAcceptDeny, setShowAcceptDeny] = useState(false);
  const messagesEndRef = useRef(null);

  const HISTORY_WINDOW = 12;

  // Centralized message handler
  const handleSendMessage = async () => {
    if (!input.trim()) return;
    const userMessage = { role: "user", content: input };
    setMessages((prev) => [...prev, userMessage]);
    setInput("");

    // Only send the last N messages as conversation history
    const windowedHistory = [...messages, userMessage].slice(-HISTORY_WINDOW);

    const requestBody = {
      message: input,
      session_id: "your-session-id", // Replace with actual session management
      conversation_history: windowedHistory,
      current_intent: currentIntent,
      pending_changes: pendingChanges,
    };

    console.log("Frontend sending request:", requestBody);

    // Call the backend unified endpoint
    const res = await fetch("http://localhost:8000/process-message", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(requestBody),
    });
    const data = await res.json();

    console.log("Frontend received response:", data);

    // Add assistant reply
    setMessages((prev) => [...prev, { role: "assistant", content: data.reply }]);
    setPendingChanges(data.pendingChanges || null);
    setCurrentIntent(data.intent || null);
    setShowAcceptDeny(data.showAcceptDeny || false);
  };

  // Handle accept action
  const handleAccept = async () => {
    if (!pendingChanges) return;
    
    // Add user confirmation message
    const confirmMessage = { role: "user", content: "Yes, that's correct" };
    setMessages((prev) => [...prev, confirmMessage]);
    
    // Clear pending changes and hide buttons immediately
    setPendingChanges(null);
    setShowAcceptDeny(false);
    
    // Send acceptance to the dedicated endpoint
    const requestBody = {
      action: "accept",
      session_id: "your-session-id",
      change_details: pendingChanges, // Send the change details that were accepted
      conversation_history: messages.slice(-HISTORY_WINDOW)
    };

    try {
      const res = await fetch("http://localhost:8000/handle-change-action", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(requestBody),
      });
      const data = await res.json();

      if (data.success) {
        // Add assistant confirmation
        setMessages((prev) => [...prev, { role: "assistant", content: data.message }]);
        setCurrentIntent(data.intent || null);
      } else {
        // Handle error
        setMessages((prev) => [...prev, { role: "assistant", content: "Sorry, there was an error processing your request." }]);
      }
    } catch (error) {
      console.error("Error handling accept:", error);
      setMessages((prev) => [...prev, { role: "assistant", content: "Sorry, there was an error processing your request." }]);
    }
  };

  // Handle deny action
  const handleDeny = async () => {
    if (!pendingChanges) return;
    
    // Add user rejection message
    const rejectMessage = { role: "user", content: "No, let me start over" };
    setMessages((prev) => [...prev, rejectMessage]);
    
    // Clear pending changes and hide buttons immediately
    setPendingChanges(null);
    setShowAcceptDeny(false);
    
    // Send denial to the dedicated endpoint
    const requestBody = {
      action: "deny",
      session_id: "your-session-id",
      change_details: pendingChanges, // Send the change details that were denied
      conversation_history: messages.slice(-HISTORY_WINDOW)
    };

    try {
      const res = await fetch("http://localhost:8000/handle-change-action", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(requestBody),
      });
      const data = await res.json();

      if (data.success) {
        // Add assistant response
        setMessages((prev) => [...prev, { role: "assistant", content: data.message }]);
        setCurrentIntent(data.intent || null);
      } else {
        // Handle error
        setMessages((prev) => [...prev, { role: "assistant", content: "Sorry, there was an error processing your request." }]);
      }
    } catch (error) {
      console.error("Error handling deny:", error);
      setMessages((prev) => [...prev, { role: "assistant", content: "Sorry, there was an error processing your request." }]);
    }
  };

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleKeyPress = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  return (
    <div className="flex flex-col h-full max-w-3xl mx-auto bg-base-100">
      {/* Chat messages */}
      <div className="flex-1 min-h-0 overflow-y-auto p-4 space-y-4 scrollbar-hide">
        {messages.map((msg, i) => (
          <div key={i} className={`chat ${msg.role === "user" ? "chat-end" : "chat-start"}`}>
            <div className="chat-bubble bg-[#444654] rounded-md p-4">
              {msg.content}
            </div>
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>

      {/* Accept/Deny UI if needed */}
      {showAcceptDeny && (
        <div className="flex justify-center gap-2 pb-4">
          <button className="btn btn-success" onClick={handleAccept}>Accept</button>
          <button className="btn btn-error" onClick={handleDeny}>Deny</button>
        </div>
      )}

      {/* Input area */}
      <div className="pb-12 bg-base-100">
        <div className="flex items-center px-10 py-5 gap-3 bg-base-200 rounded-full shadow-md">
          <textarea
            className="w-full resize-none focus:outline-none"
            rows={2}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyPress}
            placeholder="What do you want me to do?"
          />
          <button className="btn btn-neutral btn-circle" onClick={handleSendMessage}>
            <ArrowUp />
          </button>
        </div>
      </div>
    </div>
  );
};

export default Chatbox;