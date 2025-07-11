export const handleScheduleIntent = async (message, setMessages, scheduleDraft, setScheduleDraft) => {
    const response = await fetch("http://localhost:8000/propose-schedule", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message,
        prior_state: scheduleDraft,
        }),
    });
  
    const proposal = await response.json();
    // console.log(proposal.confirmation_message )
    setScheduleDraft(proposal);

    if (proposal.missing_fields.length === 0) {
        setMessages((prev) => [
          ...prev,
          { role: "assistant", content: `All set! Scheduling "${proposal.title}" at ${proposal.start_time}` }
        ]);
        // TODO: call actual Google Calendar endpoint here
        return;
      }
  
    setMessages((prev) => [
      ...prev,
      { role: "assistant", content: proposal.confirmation_message }
    ]);

  };