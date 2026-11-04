// Estado que devuelven las Server Actions de acceso a sus formularios. Viaja de vuelta al navegador: NUNCA lleva contraseñas.
export type FormState = {
  status: "idle" | "error" | "sent";
  /** Mensaje general: resumen de error o confirmación de envío. */
  message?: string;
  fieldErrors?: Partial<Record<string, string>>;
  /** Valores no sensibles para repoblar el formulario (React 19 vacía los campos tras una acción). */
  values?: Record<string, string>;
};

export const initialFormState: FormState = { status: "idle" };
