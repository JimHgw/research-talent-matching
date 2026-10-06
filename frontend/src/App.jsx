import React, { useEffect, useState } from 'react';
import { api } from './api/client.js';
import { Brand, ErrorNotice, Loading } from './shared/ui.jsx';
import { useResource } from './shared/hooks.js';
import Login from './features/auth/Login.jsx';
import Workspace from './layout/Workspace.jsx';
import { workspaceConfiguration } from './app/workspace-config.jsx';

export default function App({ configuration = workspaceConfiguration }) {
  const resource = useResource(api.session);
  const [user, setUser] = useState(null);
  useEffect(() => {
    if (resource.data) setUser(resource.data.user);
  }, [resource.data]);
  if (resource.loading)
    return (
      <main className="app-loading">
        <Brand />
        <Loading />
      </main>
    );
  if (resource.error)
    return (
      <main className="fatal">
        <Brand />
        <h1>We could not reach your workspace.</h1>
        <ErrorNotice error={resource.error} retry={resource.refresh} />
        <p>The service is currently unavailable. Please try again shortly.</p>
      </main>
    );
  return user ? (
    <Workspace
      configuration={configuration}
      key={user.id}
      user={user}
      onLogout={() => {
        setUser(null);
        resource.refresh();
      }}
    />
  ) : (
    <Login onLogin={setUser} />
  );
}
