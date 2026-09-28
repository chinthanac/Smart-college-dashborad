import { useEffect, useState } from 'react';
import { apiErrorMessage } from '../services/timetableService';

/**
 * Loads a detail panel's data after its modal has already painted.
 *
 * The modal opens from a row the list already holds, so the identity fields
 * render on the first frame and only the extra panel waits on the network.
 * Nothing about opening a record should block on a request.
 */
export default function useAsyncPanel(loader, deps, { enabled = true } = {}) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(enabled);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!enabled) {
      setLoading(false);
      return undefined;
    }

    // A modal can be closed and reopened on another row before the first
    // request lands; without this the older response would overwrite the
    // newer one.
    let live = true;
    setLoading(true);
    setError('');

    loader()
      .then((result) => {
        if (live) setData(result);
      })
      .catch((err) => {
        if (live) setError(apiErrorMessage(err, 'Could not load this section.'));
      })
      .finally(() => {
        if (live) setLoading(false);
      });

    return () => {
      live = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  return { data, loading, error };
}
