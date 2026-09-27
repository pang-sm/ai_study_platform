import { useState, type FormEvent } from 'react';
import { Button } from '@/components/ui/button';

/** How many question numbers are on screen at once. */
const GROUP_SIZE = 10;

/**
 * The question strip: ten numbers at a time, and a way to reach any of them.
 *
 * A chapter practice set runs to about 170 questions, and the strip used to draw every one of
 * them: a column of numbers taller than the page beside it, of which two were ever relevant —
 * where you are and how far the set goes. Ten is enough to see the neighbourhood and step
 * through it, and the group controls mean the rest is still one press away.
 *
 * The jump field is what makes the grouping honest rather than a limitation: "跳至第 N 题" reaches
 * any question directly, so a learner who knows they want question 137 does not page through
 * thirteen groups to get there.
 *
 * The group follows the current question. Moving with 上一题 / 下一题 across a boundary has to
 * bring the numbers with it — a strip that stayed on 1–10 while the question advanced to 11 would
 * be showing a range the current question is not in.
 */
export function PracticeQuestionNavigator({
  total,
  currentIndex,
  isAnswered,
  onSelect,
}: {
  total: number;
  currentIndex: number;
  /** Whether the question at an index already carries an answer, for the answered mark. */
  isAnswered: (index: number) => boolean;
  onSelect: (index: number) => void;
}) {
  const [group, setGroup] = useState(() => Math.floor(currentIndex / GROUP_SIZE));
  const [jump, setJump] = useState('');
  // The group follows the current question so that stepping past a boundary brings the numbers
  // with it. Adjusted during render rather than in an effect — React's own pattern for state
  // that resets when a prop changes: the effect version cascades a second render for a value
  // that was derivable from the render already in flight.
  const [lastIndex, setLastIndex] = useState(currentIndex);
  if (currentIndex !== lastIndex) {
    setLastIndex(currentIndex);
    setGroup(Math.floor(currentIndex / GROUP_SIZE));
  }

  const groupCount = Math.max(1, Math.ceil(total / GROUP_SIZE));
  const clampedGroup = Math.min(group, groupCount - 1);
  const first = clampedGroup * GROUP_SIZE;
  const last = Math.min(first + GROUP_SIZE, total);
  const numbers = Array.from({ length: Math.max(0, last - first) }, (_, offset) => first + offset);

  const jumpTo = (event: FormEvent) => {
    event.preventDefault();
    const wanted = Number.parseInt(jump, 10);
    if (!Number.isFinite(wanted)) return;
    const index = Math.min(Math.max(wanted, 1), total) - 1;
    setJump('');
    onSelect(index);
  };

  return (
    <nav className="practice-navigator" aria-label="题目导航">
      <p className="practice-navigator__count">本次 {total} 题</p>
      <p className="practice-navigator__range">
        第 {first + 1}–{last} 题
      </p>

      <div className="practice-navigator__group">
        <button
          type="button"
          className="practice-navigator__step"
          disabled={clampedGroup === 0}
          onClick={() => setGroup(clampedGroup - 1)}
        >
          上一组
        </button>

        <div className="practice-navigator__numbers">
          {numbers.map((index) => (
            <button
              key={index}
              type="button"
              aria-current={index === currentIndex ? 'step' : undefined}
              aria-label={`第 ${index + 1} 题${isAnswered(index) ? '（已作答）' : ''}`}
              className={isAnswered(index) ? 'is-answered' : undefined}
              onClick={() => onSelect(index)}
            >
              {String(index + 1).padStart(2, '0')}
            </button>
          ))}
        </div>

        <button
          type="button"
          className="practice-navigator__step"
          disabled={clampedGroup >= groupCount - 1}
          onClick={() => setGroup(clampedGroup + 1)}
        >
          下一组
        </button>
      </div>

      <form className="practice-navigator__jump" onSubmit={jumpTo}>
        <label htmlFor="jump-to-question">跳至第</label>
        <input
          id="jump-to-question"
          type="number"
          inputMode="numeric"
          min={1}
          max={total}
          value={jump}
          onChange={(event) => setJump(event.target.value)}
          placeholder={String(currentIndex + 1)}
        />
        <span>题</span>
        <Button type="submit" variant="ghost" disabled={!jump.trim()}>
          跳转
        </Button>
      </form>
    </nav>
  );
}
