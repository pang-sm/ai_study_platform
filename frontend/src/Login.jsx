import { useState } from "react";

export default function Login({ onLogin }) {
  const [name, setName] = useState("");
  const [year, setYear] = useState("大一");
  const [major, setMajor] = useState("软件工程");
  const [habit, setHabit] = useState("每天学习1-2小时");

  const handleSubmit = (e) => {
    e.preventDefault();
    onLogin({ name, year, major, habit });
  };

  return (
    <div style={{ padding: "40px", fontFamily: "Arial" }}>
      <h2>欢迎使用 AI 学习助手</h2>
      <form onSubmit={handleSubmit}>
        <div>
          <label>姓名:</label>
          <input value={name} onChange={e => setName(e.target.value)} required/>
        </div>
        <div>
          <label>年级:</label>
          <select value={year} onChange={e => setYear(e.target.value)}>
            <option>大一</option>
            <option>大二</option>
            <option>大三</option>
            <option>大四</option>
          </select>
        </div>
        <div>
          <label>专业:</label>
          <input value={major} onChange={e => setMajor(e.target.value)}/>
        </div>
        <div>
          <label>学习习惯:</label>
          <input value={habit} onChange={e => setHabit(e.target.value)}/>
        </div>
        <button type="submit" style={{ marginTop: "20px" }}>进入学习助手</button>
      </form>
    </div>
  );
}