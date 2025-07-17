import { useEffect, useState } from "react";

export default function TodoPage() {
  const [todos, setTodos] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("http://localhost:8000/todo/get-todos") // replace with your actual backend URL
      .then((res) => res.json())
      .then((data) => {
        setTodos(data);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  if (loading) return <div className="text-center mt-8">Loading...</div>;

  return (
    <div className="max-w-2xl mx-auto p-6">
      <h1 className="text-2xl font-bold mb-4">Your Todos</h1>
      <ul className="space-y-3">
        {todos.map((todo) => (
          <li key={todo.id} className="flex justify-between items-center bg-white p-4 rounded shadow">
            <span className={todo.completed ? "line-through text-base-200" : "text-base-300"}>
              {todo.title}
            </span>
            <span className={`text-sm px-2 py-1 rounded ${todo.completed ? "bg-green-100 text-green-700" : "bg-yellow-100 text-yellow-700"}`}>
              {todo.completed ? "Done" : "Pending"}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
