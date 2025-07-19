import { useEffect, useState } from "react";
import Cookies from 'js-cookie';

export default function TodoPage() {
  const [todos, setTodos] = useState([]);
  const [loading, setLoading] = useState(true);
  const [email, setEmail] = useState(null);

  useEffect( () => {
    setEmail(Cookies.get("email"))

    fetch(`http://localhost:8000/todo/get-todos?email=${Cookies.get("email")}`) 
      .then((res) => res.json())
      .then((data) => {
        setTodos(data);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  const handleToggle = async (id, email, status) => {
    setTodos((prevTodos) =>
        prevTodos.map((todo) =>
          todo.id === id ? { ...todo, completed: !status } : todo
        )
    );
    await fetch("http://localhost:8000/todo/update-todos-completed", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: email,
          id: id,
          completed: status
        })
      });

  }

  if (loading) return <div className="text-center mt-8">Loading...</div>;

  return (
    <div className="max-w-2xl mx-auto p-6">
    <h1 className="text-3xl font-bold mb-6 text-center">📝 Your Todo List</h1>
    <ul className="space-y-4">
        {todos.map((todo) => (
        <li
            key={todo.id}
            className="flex items-center justify-between p-4 bg-base-100 rounded-xl shadow border border-base-200 hover:shadow-md transition"
        >
            <label className="flex items-center gap-3 cursor-pointer w-full">
            <input
                type="checkbox"
                checked={todo.completed}
                onChange={() => handleToggle(todo.id, email, todo.completed)} // You define this toggle handler
                className="checkbox checkbox-primary"
            />
            <span className={`flex-1 text-lg transition-all duration-200 ${todo.completed ? "line-through text-base-300" : "text-base-content"}`}>
                {todo.title}
            </span>
            </label>
        </li>
        ))}
    </ul>
    </div>

  );
}
