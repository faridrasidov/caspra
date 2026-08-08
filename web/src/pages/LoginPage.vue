<script setup lang="ts">
import { RiLockPasswordLine } from "@remixicon/vue";
import { ref } from "vue";

import { ApiError } from "../api/client";
import { useAuth } from "../auth/useAuth";
import FormField from "../components/FormField.vue";
import UiButton from "../components/UiButton.vue";

const { login } = useAuth();
const email = ref("");
const password = ref("");
const error = ref("");
const submitting = ref(false);

async function submit() {
  error.value = "";
  submitting.value = true;
  try {
    await login(email.value, password.value);
  } catch (caught) {
    error.value =
      caught instanceof ApiError ? caught.message : "Sign in could not be completed";
  } finally {
    submitting.value = false;
  }
}
</script>

<template>
  <main class="grid min-h-screen grid-cols-[minmax(280px,.75fr)_minmax(420px,1.25fr)] bg-white max-[760px]:grid-cols-1">
    <section class="flex flex-col justify-center bg-sidebar p-[clamp(36px,7vw,96px)] text-white max-[760px]:min-h-[220px] max-[760px]:p-[34px]">
      <div class="mb-[22px] grid size-[58px] place-items-center rounded-md bg-primary text-[28px] font-extrabold max-[760px]:mb-3.5 max-[760px]:size-[46px] max-[760px]:text-[22px]">C</div>
      <h1 class="text-[32px] font-bold max-[760px]:text-[26px]">CASPRA</h1>
      <p class="mt-2 text-[13px] text-[#b8bec4]">Stored-value operations</p>
    </section>
    <section class="grid place-items-center p-8 max-[760px]:items-start max-[760px]:p-[34px_22px]">
      <form class="grid w-full max-w-[380px] gap-[18px]" @submit.prevent="submit">
        <div class="mb-2 flex items-start gap-3">
          <RiLockPasswordLine aria-hidden="true" class="size-[22px] text-primary" />
          <div>
            <h2 class="text-xl font-bold">Operator sign in</h2>
            <p class="mt-1 text-[11px] text-muted">Use your organization credentials.</p>
          </div>
        </div>
        <FormField label="Email">
          <input v-model="email" type="email" autocomplete="username" required />
        </FormField>
        <FormField label="Password">
          <input v-model="password" type="password" autocomplete="current-password" required />
        </FormField>
        <p v-if="error" class="text-[12px] text-danger" role="alert">{{ error }}</p>
        <UiButton type="submit" :disabled="submitting">
          {{ submitting ? "Signing in..." : "Sign in" }}
        </UiButton>
      </form>
    </section>
  </main>
</template>
