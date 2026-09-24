import { genderLabels, type Gender } from "@/lib/gender";

export function GenderSelect({ value, onChange }: { value: Gender; onChange: (value: Gender) => void }) {
  return <label className="mt-4 block text-sm">Género (opcional)
    <select className="mt-1 h-11 w-full rounded-lg border border-current/20 bg-transparent px-3" value={value}
      onChange={(e) => onChange(e.target.value as Gender)}>
      {Object.entries(genderLabels).map(([key, label]) => <option className="bg-paper text-ink" key={key} value={key}>{label}</option>)}
    </select>
    <span className="mt-2 block text-xs opacity-70">Puedes cambiarlo o retirarlo. Se utiliza para personalizar contenido, anuncios y estadísticas.</span>
  </label>;
}
