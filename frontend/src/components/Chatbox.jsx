import React from 'react'
import { useState, useRef, useEffect } from "react";
import { ArrowUp } from 'lucide-react';
import { handleScheduleIntent } from '../handlers/intenthandlers';

const Chatbox = () => {
    const [messages, setMessages] = useState([]);
    const [scheduleDraft, _setScheduleDraft] = useState([]);
    const scheduleDraftRef = useRef(null);
    const setScheduleDraft = (draft) => {
    scheduleDraftRef.current = draft;   // keep latest in ref
    _setScheduleDraft(draft);
    };
    const [input, setInput] = useState("");
    const [currentIntent, setCurrentIntent] = useState(null);
    const messagesEndRef = useRef(null);

    const processMessage = async (newMessage) =>
    {
        try {
            // Classify intent
            const intentRes = await fetch("http://localhost:8000/classify-intent", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ message: newMessage.content }),
            });
        
            const { intent } = await intentRes.json();
        
            // 🧠 Step 2: Route based on intent
            switch (intent) {
              case "Schedule":
                setCurrentIntent("Schedule")
                await handleScheduleIntent(newMessage.content, setMessages, scheduleDraftRef.current, setScheduleDraft);
                break;
            //   case "Email":
            //     await handleEmailIntent(newMessage);
            //     break;
            //   case "Remind":
            //     await handleReminderIntent(newMessage);
            //     break;
            //   case "General":
            //   default:
            //     await handleGeneralIntent(newMessage);
            //     break;
            }
          } catch (error) {
            console.error("Intent classification failed:", error);
            setMessages((prev) => [
              ...prev,
              { role: "assistant", content: "Oops! Something went wrong. Try again later." },
            ]);
          }
    }

    const sendMessage = async () => {
        if (!input.trim()) return;
    
        const newMessage = { role: "user", content: input };
        setMessages((prev) => [...prev, newMessage]);
        setInput("");
        if (!currentIntent) {
            await processMessage(newMessage);
        } else {
            const res = await fetch("http://localhost:8000/follow-up-intent", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ current_intent: currentIntent, message: newMessage.content }),
              });
              const { decision } = await res.json();
            if (decision === "EXIT") {
                setCurrentIntent(null);
                setScheduleDraft(null);
                await processMessage(newMessage);
            }
            else 
            {
                switch (currentIntent) {
                    case "Schedule":
                      await handleScheduleIntent(newMessage.content, setMessages, scheduleDraftRef.current, setScheduleDraft);
                      break;
                  //   case "Email":
                  //     await handleEmailIntent(newMessage);
                  //     break;
                  //   case "Remind":
                  //     await handleReminderIntent(newMessage);
                  //     break;
                  //   case "General":
                  //   default:
                  //     await handleGeneralIntent(newMessage);
                  //     break;
                  }
            }
            
        }
        
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