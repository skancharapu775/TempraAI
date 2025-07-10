import React from 'react'
import { useState, useRef, useEffect } from "react";
import { ArrowUp } from 'lucide-react';

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
    <div className="flex flex-col h-full max-w-3xl mx-auto bg-base-100">
    {/* Chat messages */}
    <div className="flex-1 min-h-0 overflow-y-auto p-4 space-y-4 scrollbar-hide">
      {messages.map((msg, i) => (
        <div key={i} className={`chat ${msg.role === "user" ? "chat-end" : "chat-start"}`}>
          <div
            className="chat-bubble bg-[#444654] rounded-md p-4"
          >
            {msg.content}
          </div>
        </div>
      ))}
      <div ref={messagesEndRef} />
    </div>

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
            <button className="btn btn-neutral btn-circle" onClick={sendMessage}>
            <ArrowUp/>
            </button>
      </div>
    </div>
  </div>
  )
}

export default Chatbox