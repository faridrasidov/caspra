import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type PropsWithChildren,
} from "react";

import {
  apiRequest,
  refreshAccessToken,
  setAccessToken,
  type MeOut,
  type Schemas,
  type TokenOut,
} from "../api/client";

type AuthContextValue = {
  loading: boolean;
  user: MeOut | null;
  permissions: Set<string>;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  reloadIdentity: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: PropsWithChildren) {
  const [loading, setLoading] = useState(true);
  const [user, setUser] = useState<MeOut | null>(null);
  const [permissions, setPermissions] = useState<Set<string>>(new Set());

  const reloadIdentity = useCallback(async () => {
    const [profile, permissionResult] = await Promise.all([
      apiRequest<MeOut>("/admin/api/v1/auth/me"),
      apiRequest<Schemas["PermissionsOut"]>("/admin/api/v1/auth/permissions"),
    ]);
    setUser(profile);
    setPermissions(new Set(permissionResult.permissions));
  }, []);

  useEffect(() => {
    let active = true;
    refreshAccessToken()
      .then(async (token) => {
        if (token && active) await reloadIdentity();
      })
      .catch(() => undefined)
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [reloadIdentity]);

  const login = useCallback(
    async (email: string, password: string) => {
      const tokens = await apiRequest<TokenOut>(
        "/admin/api/v1/auth/login",
        {
          method: "POST",
          body: JSON.stringify({ email, password }),
        },
        false,
      );
      setAccessToken(tokens.access_token);
      await reloadIdentity();
    },
    [reloadIdentity],
  );

  const logout = useCallback(async () => {
    try {
      await apiRequest<void>("/admin/api/v1/auth/logout", { method: "POST" });
    } finally {
      setAccessToken(null);
      setUser(null);
      setPermissions(new Set());
    }
  }, []);

  const value = useMemo(
    () => ({ loading, user, permissions, login, logout, reloadIdentity }),
    [loading, user, permissions, login, logout, reloadIdentity],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used within AuthProvider");
  return context;
}
