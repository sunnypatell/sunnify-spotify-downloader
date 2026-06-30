import type { AnyFieldApi } from "@tanstack/react-form";

export const tanstackFormUtils = {
  isFieldInvalid: (fieldApi: AnyFieldApi) => fieldApi.state.meta.isTouched && !fieldApi.state.meta.isValid
};
