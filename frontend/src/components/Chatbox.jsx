import React from 'react'
import { useState, useRef, useEffect } from "react";
import Navbar from './Navbar';

const Chatbox = () => {
    const [messages, setMessages] = useState([]);
    const [input, setInput] = useState("");
    const messagesEndRef = useRef(null);
    const sendMessage = () => {
        if (!input.trim()) return;
    
        const newMessage = { role: "user", content: input };
        setMessages((prev) => [...prev, newMessage]);
        setTimeout(() => {
            setMessages((prev) => [
              ...prev,
              { role: "user", content: input },
              { role: "assistant", content: "Processing your request..." },
            ]);
          }, 300);

        setInput("");
    }
    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
      }, [messages]);

    const handleKeyPress = (e) => {
        if (e.key === "Enter" && !e.shiftKey) {
          e.preventDefault();
          sendMessage();
        }
      };
  return (
    <div className="flex flex-col h-full max-w-2xl mx-auto bg-base-100">
    {/* Chat messages */}
    <div className="flex-1 min-h-0 overflow-y-auto p-4 space-y-4 scrollbar-hide">
      {messages.map((msg, i) => (
        <div key={i} className={`chat ${msg.role === "user" ? "chat-end" : "chat-start"}`}>
          <div
            className={`chat-bubble ${
              msg.role === "user" ? "chat-bubble-primary" : "chat-bubble-secondary"
            }`}
          >
            {msg.content}
          </div>
        </div>
      ))}
      <div ref={messagesEndRef} />
    </div>

    {/* Input area */}
    <div className="p-4 border-t bg-base-100 flex gap-2">
      <textarea
        className="textarea textarea-bordered w-full resize-none"
        rows={2}
        value={input}
        onChange={(e) => setInput(e.target.value)}
        onKeyDown={handleKeyPress}
        placeholder="What do you want me to do?"
      />
      <button className="btn btn-neutral" onClick={sendMessage}>
        Send
      </button>
    </div>
  </div>
  )
}

export default Chatbox