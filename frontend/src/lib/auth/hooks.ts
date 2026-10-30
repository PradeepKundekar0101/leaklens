"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useSyncExternalStore } from "react";

import { api, type Schemas } from "@/lib/api/client";
import { isUnauthorized, unwrap } from "@/lib/api/errors";

import { isRole, type Role } from "./roles";

export type User = Omit<Schemas["UserOut"], "role"> & { role: Role };

export const meQueryKey = ["auth", "me"] as const;
export const loginMutationKey = ["auth", "login"] as const;

function toUser(raw: Schemas["UserOut"]): User {
  if (!isRole(raw.role)) {
    throw new Error(`Unknown role "${raw.role}" for ${raw.email}.`);
  }
  return { ...raw, role: raw.role };
}

async function fetchMe(): Promise<User | null> {
  try {
    return toUser(unwrap(await api.GET("/api/v1/auth/me")));
  } catch (error) {
    if (isUnauthorized(error)) return null;
    throw error;
  }
}

/**
 * The signed-in user. `data` is `null` when there is no valid session and `undefined`
 * while loading.
 */
export function useMe() {
  const query = useQuery({
    queryKey: meQueryKey,
    queryFn: fetchMe,
    staleTime: 5 * 60_000,
    retry: (count, error) => !isUnauthorized(error) && count < 2,
  });
  // The server never knows the user. While a streamed segment hydrates, report "loading"
  // even if the client already has the user, so role-dependent markup matches the HTML.
  const hydrated = useHydrated();
  return hydrated ? query : { ...query, data: undefined, isSuccess: false, isPending: true as const };
}

const noopSubscribe = () => () => {};

/** False during server render and hydration, true afterwards. */
export function useHydrated(): boolean {
  return useSyncExternalStore(
    noopSubscribe,
    () => true,
    () => false,
  );
}

export function useLogin() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationKey: loginMutationKey,
    mutationFn: async (body: Schemas["LoginIn"]) =>
      toUser(unwrap(await api.POST("/api/v1/auth/login", { body }))),
    onSuccess: (user) => {
      queryClient.clear();
      queryClient.setQueryData(meQueryKey, user);
    },
  });
}

export function useLogout() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const result = await api.POST("/api/v1/auth/logout");
      // An expired session is already logged out.
      if (!result.response.ok && result.response.status !== 401) unwrap(result);
    },
    onSettled: () => {
      queryClient.clear();
      queryClient.setQueryData(meQueryKey, null);
    },
  });
}
