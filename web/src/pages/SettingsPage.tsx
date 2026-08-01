import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { LogOut, Save } from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";

import { apiRequest, type Schemas } from "../api/client";
import { useAuth } from "../auth/AuthProvider";
import {
  Button,
  ErrorState,
  FormField,
  LoadingState,
  PageHeader,
} from "../components/ui";

export function SettingsPage() {
  const queryClient = useQueryClient();
  const { logout } = useAuth();
  const settings = useQuery({
    queryKey: ["org-settings"],
    queryFn: () =>
      apiRequest<Schemas["OrgSettingsOut"]>("/admin/api/v1/org/settings"),
  });
  const [timezone, setTimezone] = useState("UTC");
  useEffect(() => {
    if (settings.data) setTimezone(settings.data.timezone);
  }, [settings.data]);
  const save = useMutation({
    mutationFn: () =>
      apiRequest("/admin/api/v1/org/settings", {
        method: "PATCH",
        body: JSON.stringify({ timezone }),
      }),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["org-settings"] }),
  });
  const revokeSessions = useMutation({
    mutationFn: () =>
      apiRequest<void>("/admin/api/v1/auth/sessions/revoke-all", {
        method: "POST",
      }),
    onSuccess: logout,
  });
  if (settings.isLoading) return <LoadingState />;
  if (settings.error) return <ErrorState message={settings.error.message} />;
  return (
    <div>
      <PageHeader
        title="Settings"
        description="Organization defaults and operator session controls."
      />
      <form
        className="settings-form"
        onSubmit={(event: FormEvent) => {
          event.preventDefault();
          save.mutate();
        }}
      >
        <section>
          <h2>Regional settings</h2>
          <FormField label="Timezone">
            <input
              value={timezone}
              onChange={(event) => setTimezone(event.target.value)}
              required
            />
          </FormField>
        </section>
        <section>
          <h2>Session security</h2>
          <Button
            icon={LogOut}
            type="button"
            variant="secondary"
            disabled={revokeSessions.isPending}
            onClick={() => revokeSessions.mutate()}
          >
            Revoke all sessions
          </Button>
        </section>
        <footer>
          <Button icon={Save} type="submit" disabled={save.isPending}>
            {save.isPending ? "Saving..." : "Save settings"}
          </Button>
        </footer>
      </form>
    </div>
  );
}
