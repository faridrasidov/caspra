<script setup lang="ts">
import { RiLogoutBoxRLine, RiSaveLine } from "@remixicon/vue";
import { useMutation, useQuery, useQueryClient } from "@tanstack/vue-query";
import { computed, ref, watch } from "vue";

import { apiRequest, type Schemas } from "../api/client";
import { useAuth } from "../auth/useAuth";
import DataState from "../components/DataState.vue";
import FormField from "../components/FormField.vue";
import PageHeader from "../components/PageHeader.vue";
import UiButton from "../components/UiButton.vue";

const queryClient = useQueryClient();
const { logout } = useAuth();

const org = useQuery({
  queryKey: ["org"],
  queryFn: () => apiRequest<Schemas["OrganizationOut"]>("/admin/api/v1/org"),
});
const settings = useQuery({
  queryKey: ["settings"],
  queryFn: () => apiRequest<Schemas["OrgSettingsOut"]>("/admin/api/v1/settings"),
});
const billing = useQuery({
  queryKey: ["settings-billing"],
  queryFn: () => apiRequest<Schemas["BillingSettingsOut"]>("/admin/api/v1/settings/billing"),
});
const security = useQuery({
  queryKey: ["settings-security"],
  queryFn: () => apiRequest<Schemas["SecuritySettingsOut"]>("/admin/api/v1/settings/security"),
});

const orgForm = ref({
  name: "",
  defaultCurrency: "",
  status: "",
  slug: "",
});
const settingsForm = ref({
  timezone: "",
  configText: "",
  brandingText: "",
});
const billingForm = ref({
  plan: "",
  billingEmail: "",
  currency: "",
  paymentMethodText: "",
});
const securityForm = ref({
  mfaRequired: false,
  sessionTimeoutMinutes: 0,
  passwordPolicyText: "",
  ipAllowlistText: "",
});

function toJsonText(value: unknown) {
  if (value === null || value === undefined) return "";
  return JSON.stringify(value, null, 2);
}

function parseOptionalJson(raw: string, label: string) {
  const trimmed = raw.trim();
  if (!trimmed) return null;
  try {
    return JSON.parse(trimmed);
  } catch {
    throw new Error(`${label} must be valid JSON`);
  }
}

watch(
  () => org.data.value,
  (value) => {
    if (!value) return;
    orgForm.value.name = value.name;
    orgForm.value.defaultCurrency = value.default_currency;
    orgForm.value.status = value.status;
    orgForm.value.slug = value.slug;
  },
  { immediate: true },
);

watch(
  () => settings.data.value,
  (value) => {
    if (!value) return;
    settingsForm.value.timezone = value.timezone;
    settingsForm.value.configText = toJsonText(value.config);
    settingsForm.value.brandingText = toJsonText(value.branding);
  },
  { immediate: true },
);

watch(
  () => billing.data.value,
  (value) => {
    if (!value) return;
    billingForm.value.plan = value.plan;
    billingForm.value.billingEmail = value.billing_email ?? "";
    billingForm.value.currency = value.currency;
    billingForm.value.paymentMethodText = toJsonText(value.payment_method);
  },
  { immediate: true },
);

watch(
  () => security.data.value,
  (value) => {
    if (!value) return;
    securityForm.value.mfaRequired = value.mfa_required;
    securityForm.value.sessionTimeoutMinutes = value.session_timeout_minutes;
    securityForm.value.passwordPolicyText = toJsonText(value.password_policy);
    securityForm.value.ipAllowlistText = (value.ip_allowlist ?? []).join("\n");
  },
  { immediate: true },
);

const loading = computed(
  () =>
    org.isLoading.value ||
    settings.isLoading.value ||
    billing.isLoading.value ||
    security.isLoading.value,
);
const loadError = computed(
  () =>
    org.error.value ?? settings.error.value ?? billing.error.value ?? security.error.value,
);

const saveOrg = useMutation({
  mutationFn: () =>
    apiRequest<Schemas["OrganizationOut"]>("/admin/api/v1/org", {
      method: "PATCH",
      body: JSON.stringify({
        name: orgForm.value.name.trim() || null,
        default_currency: orgForm.value.defaultCurrency.trim() || null,
      }),
    }),
  onSuccess: () => queryClient.invalidateQueries({ queryKey: ["org"] }),
});

const saveSettings = useMutation({
  mutationFn: () => {
    const config = parseOptionalJson(settingsForm.value.configText, "Config");
    const branding = parseOptionalJson(settingsForm.value.brandingText, "Branding");

    return apiRequest<Schemas["OrgSettingsOut"]>("/admin/api/v1/settings", {
      method: "PUT",
      body: JSON.stringify({
        timezone: settingsForm.value.timezone.trim() || null,
        config,
        branding,
      }),
    });
  },
  onSuccess: () => queryClient.invalidateQueries({ queryKey: ["settings"] }),
});

const saveBilling = useMutation({
  mutationFn: () => {
    const paymentMethod = parseOptionalJson(
      billingForm.value.paymentMethodText,
      "Payment method",
    );

    return apiRequest<Schemas["BillingSettingsOut"]>("/admin/api/v1/settings/billing", {
      method: "PUT",
      body: JSON.stringify({
        plan: billingForm.value.plan.trim() || null,
        billing_email: billingForm.value.billingEmail.trim() || null,
        currency: billingForm.value.currency.trim() || null,
        payment_method: paymentMethod,
      }),
    });
  },
  onSuccess: () => queryClient.invalidateQueries({ queryKey: ["settings-billing"] }),
});

const saveSecurity = useMutation({
  mutationFn: () => {
    const timeout = Number(securityForm.value.sessionTimeoutMinutes);
    if (!Number.isInteger(timeout) || timeout <= 0) {
      throw new Error("Session timeout must be a positive whole number");
    }
    const passwordPolicy = parseOptionalJson(
      securityForm.value.passwordPolicyText,
      "Password policy",
    );
    const ipAllowlist = securityForm.value.ipAllowlistText
      .split(/[\n,]/)
      .map((entry) => entry.trim())
      .filter(Boolean);

    return apiRequest<Schemas["SecuritySettingsOut"]>("/admin/api/v1/settings/security", {
      method: "PUT",
      body: JSON.stringify({
        mfa_required: securityForm.value.mfaRequired,
        session_timeout_minutes: timeout,
        password_policy: passwordPolicy,
        ip_allowlist: ipAllowlist.length ? ipAllowlist : null,
      }),
    });
  },
  onSuccess: () => queryClient.invalidateQueries({ queryKey: ["settings-security"] }),
});

const revokeSessions = useMutation({
  mutationFn: () =>
    apiRequest<void>("/admin/api/v1/auth/sessions/revoke-all", { method: "POST" }),
  onSuccess: logout,
});
</script>

<template>
  <DataState v-if="loading" />
  <DataState
    v-else-if="loadError"
    kind="error"
    :message="loadError.message"
    retry
    @retry="() => { org.refetch(); settings.refetch(); billing.refetch(); security.refetch(); }"
  />
  <div v-else>
    <PageHeader
      title="Settings"
      description="Organization profile, tenant settings, billing, security, and admin session actions."
    />
    <form class="overflow-hidden rounded-md border border-line bg-white" @submit.prevent="saveOrg.mutate()">
      <section class="grid gap-4 border-b border-line p-5">
        <h2 class="text-[13px] font-bold">Organization</h2>
        <div class="grid gap-4 md:grid-cols-2">
          <FormField label="Name"><input v-model="orgForm.name" required /></FormField>
          <FormField label="Default currency"><input v-model="orgForm.defaultCurrency" required /></FormField>
        </div>
        <div class="grid gap-4 md:grid-cols-2">
          <FormField label="Status">
            <input :value="orgForm.status" disabled />
          </FormField>
          <FormField label="Slug">
            <input :value="orgForm.slug" disabled />
          </FormField>
        </div>
      </section>
      <footer class="flex items-center justify-between gap-3 bg-subtle px-5 py-3.5">
        <p v-if="saveOrg.error.value" class="text-[12px] text-danger" role="alert">{{ saveOrg.error.value.message }}</p>
        <UiButton :icon="RiSaveLine" type="submit" :disabled="saveOrg.isPending.value">
          {{ saveOrg.isPending.value ? "Saving..." : "Save organization" }}
        </UiButton>
      </footer>
    </form>

    <form class="mt-4 overflow-hidden rounded-md border border-line bg-white" @submit.prevent="saveSettings.mutate()">
      <section class="grid gap-4 border-b border-line p-5">
        <h2 class="text-[13px] font-bold">General settings</h2>
        <FormField label="Timezone"><input v-model="settingsForm.timezone" required /></FormField>
        <FormField label="Config JSON (optional)">
          <textarea v-model="settingsForm.configText" rows="6" placeholder='{"feature_flag": true}' />
        </FormField>
        <FormField label="Branding JSON (optional)">
          <textarea v-model="settingsForm.brandingText" rows="6" placeholder='{"theme": "dark"}' />
        </FormField>
      </section>
      <footer class="flex items-center justify-between gap-3 bg-subtle px-5 py-3.5">
        <p v-if="saveSettings.error.value" class="text-[12px] text-danger" role="alert">{{ saveSettings.error.value.message }}</p>
        <UiButton :icon="RiSaveLine" type="submit" :disabled="saveSettings.isPending.value">
          {{ saveSettings.isPending.value ? "Saving..." : "Save settings" }}
        </UiButton>
      </footer>
    </form>

    <form class="mt-4 overflow-hidden rounded-md border border-line bg-white" @submit.prevent="saveBilling.mutate()">
      <section class="grid gap-4 border-b border-line p-5">
        <h2 class="text-[13px] font-bold">Billing</h2>
        <FormField label="Plan"><input v-model="billingForm.plan" required /></FormField>
        <FormField label="Billing email"><input v-model="billingForm.billingEmail" type="email" /></FormField>
        <FormField label="Currency"><input v-model="billingForm.currency" required /></FormField>
        <FormField label="Payment method JSON (optional)">
          <textarea v-model="billingForm.paymentMethodText" rows="6" placeholder='{"method": "card"}' />
        </FormField>
      </section>
      <footer class="flex items-center justify-between gap-3 bg-subtle px-5 py-3.5">
        <p v-if="saveBilling.error.value" class="text-[12px] text-danger" role="alert">{{ saveBilling.error.value.message }}</p>
        <UiButton :icon="RiSaveLine" type="submit" :disabled="saveBilling.isPending.value">
          {{ saveBilling.isPending.value ? "Saving..." : "Save billing settings" }}
        </UiButton>
      </footer>
    </form>

    <form class="mt-4 overflow-hidden rounded-md border border-line bg-white" @submit.prevent="saveSecurity.mutate()">
      <section class="grid gap-4 border-b border-line p-5">
        <h2 class="text-[13px] font-bold">Security</h2>
        <label class="flex items-center gap-2 text-[12px] font-semibold text-ink">
          <input
            v-model="securityForm.mfaRequired"
            type="checkbox"
            class="size-4 border border-line-strong bg-white text-primary accent-primary checked:accent-primary focus:outline-none"
          />
          <span>Require MFA</span>
        </label>
        <FormField label="Session timeout (minutes)">
          <input v-model.number="securityForm.sessionTimeoutMinutes" type="number" min="1" required />
        </FormField>
        <FormField label="Password policy JSON (optional)">
          <textarea v-model="securityForm.passwordPolicyText" rows="6" placeholder='{"min_length": 12}' />
        </FormField>
        <FormField label="Allowed IPs (comma or newline list)">
          <textarea v-model="securityForm.ipAllowlistText" rows="5" placeholder="192.0.2.1&#10;198.51.100.0/24" />
        </FormField>
      </section>
      <footer class="flex items-center justify-between gap-3 bg-subtle px-5 py-3.5">
        <p v-if="saveSecurity.error.value" class="text-[12px] text-danger" role="alert">{{ saveSecurity.error.value.message }}</p>
        <UiButton :icon="RiSaveLine" type="submit" :disabled="saveSecurity.isPending.value">
          {{ saveSecurity.isPending.value ? "Saving..." : "Save security settings" }}
        </UiButton>
      </footer>
    </form>

    <form class="mt-4 overflow-hidden rounded-md border border-line bg-white" @submit.prevent="revokeSessions.mutate()">
      <section class="grid gap-4 border-b border-line p-5">
        <h2 class="text-[13px] font-bold">Session controls</h2>
        <div>
          <UiButton
            :icon="RiLogoutBoxRLine"
            type="button"
            variant="danger"
            :disabled="revokeSessions.isPending.value"
            @click="revokeSessions.mutate()"
          >Revoke all sessions</UiButton>
        </div>
      </section>
      <footer class="flex justify-end bg-subtle px-5 py-3.5">
        <p v-if="revokeSessions.error.value" class="text-[12px] text-danger" role="alert">{{ revokeSessions.error.value.message }}</p>
      </footer>
    </form>
  </div>
</template>
