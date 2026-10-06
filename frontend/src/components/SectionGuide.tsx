/**
 * Editing guidance shown above the ChordPro editor. It lists every section
 * directive so a user editing the output knows exactly what to type.
 */

interface Row {
  section: string;
  open: string;
  close: string;
}

const ROWS: Row[] = [
  { section: "Chorus", open: "{soc}", close: "{eoc}" },
  { section: "Verse", open: "{sov}", close: "{eov}" },
  { section: "Bridge", open: "{sob}", close: "{eob}" },
  { section: "Intro / Outro / Solo…", open: "{comment: Intro}", close: "—" },
];

export default function SectionGuide() {
  return (
    <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-xs text-slate-700 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300">
      <p className="mb-2 text-sm font-semibold text-slate-800 dark:text-slate-100">
        Editing guide
      </p>
      <p className="mb-2">
        Edit the ChordPro below. Chords go inline in square brackets, e.g.{" "}
        <code className="rounded bg-slate-200 px-1 dark:bg-slate-800">[C]Hello</code>.
        Put each section marker on its own line, and remember to close the block
        with its matching end directive.
      </p>
      <table className="w-full border-collapse">
        <thead>
          <tr className="text-left text-slate-500 dark:text-slate-400">
            <th className="py-0.5 pr-3 font-medium">Section</th>
            <th className="py-0.5 pr-3 font-medium">Open</th>
            <th className="py-0.5 font-medium">Close</th>
          </tr>
        </thead>
        <tbody>
          {ROWS.map((row) => (
            <tr key={row.section}>
              <td className="py-0.5 pr-3">{row.section}</td>
              <td className="py-0.5 pr-3">
                <code className="rounded bg-slate-200 px-1 dark:bg-slate-800">
                  {row.open}
                </code>
              </td>
              <td className="py-0.5">
                {row.close === "—" ? (
                  "—"
                ) : (
                  <code className="rounded bg-slate-200 px-1 dark:bg-slate-800">
                    {row.close}
                  </code>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="mt-2 text-slate-500 dark:text-slate-400">
        Long forms work too:{" "}
        <code className="rounded bg-slate-200 px-1 dark:bg-slate-800">
          {"{start_of_chorus}"}
        </code>{" "}
        /{" "}
        <code className="rounded bg-slate-200 px-1 dark:bg-slate-800">
          {"{end_of_chorus}"}
        </code>
        . Keep each {"{…}"} on its own line.
      </p>
    </div>
  );
}
