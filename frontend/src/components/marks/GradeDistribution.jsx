import BarList from '../charts/BarList';

/**
 * Grade bands as a ranked meter list.
 *
 * Bands with nobody in them are dropped: a row of zeros reads as a broken
 * chart rather than an empty one.
 */
export default function GradeDistribution({ bands = [], total = 0 }) {
  const rows = bands
    .filter((band) => band.student_count > 0)
    .map((band) => ({
      id: band.grade_letter,
      label: `${band.grade_letter} · ${band.grade_point} points`,
      caption: `${band.student_count} of ${total}`,
      percentage: band.percentage,
      tone: band.grade_letter === 'F' ? 'danger' : band.grade_point <= 5 ? 'warn' : undefined,
    }));

  return (
    <BarList
      rows={rows}
      emptyTitle="No grades yet"
      emptyHint="Grades appear once a student has a complete set of published marks."
    />
  );
}
