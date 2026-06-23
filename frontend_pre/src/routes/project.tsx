import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";

interface Project {
  id: string;
  name: string;
  description?: string;
  created_at?: string;
}

const ProjectList: React.FC = () => {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("/api/projects", {
      credentials: "include",
    })
      .then((res) => res.json())
      .then((data) => {
        setProjects(data);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  return (
    <div>
      <h2>项目列表</h2>
      {loading ? (
        <div>加载中...</div>
      ) : (
        <ul>
          {projects.map((project) => (
            <li key={project.id}>
              <Link to={`/projects/${project.id}`}>
                <strong>{project.name}</strong>
              </Link>
              <div>{project.description}</div>
              <div>{project.created_at}</div>
            </li>
          ))}
        </ul>
      )}
      <Link to="/projects/new">
        <button>新建项目</button>
      </Link>
    </div>
  );
};

export default ProjectList;