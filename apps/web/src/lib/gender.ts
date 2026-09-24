export type Gender = "man" | "woman" | "other" | "prefer_not_to_say" | "unspecified";
export const genderLabels: Record<Gender, string> = {
  unspecified: "Sin especificar", man: "Hombre", woman: "Mujer", other: "Otra identidad",
  prefer_not_to_say: "Prefiero no decirlo",
};
