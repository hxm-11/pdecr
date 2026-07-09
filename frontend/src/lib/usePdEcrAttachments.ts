import { useCallback, useEffect, useState } from "react";

import {
  deletePdEcrAttachment,
  listPdEcrAttachments,
  pdEcrAttachmentDownloadUrl,
  uploadPdEcrAttachment,
  type PdEcrAttachment,
  type PdEcrAttachmentSection,
} from "./pdEcrApi";

const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/** A working record id is a real backend case only when it's a UUID. */
export function isBackendCaseId(id?: string | null): boolean {
  return !!id && UUID_RE.test(id.trim());
}

export type UiAttachment = {
  /** Present when the file is persisted in the backend. */
  id?: string;
  name: string;
  type: string;
  size: number;
  previewUrl?: string;
  downloadUrl?: string;
};

function toUi(a: PdEcrAttachment): UiAttachment {
  const url = pdEcrAttachmentDownloadUrl(a.id);
  const isImage = (a.content_type || "").startsWith("image/");
  return {
    id: a.id,
    name: a.filename,
    type: a.content_type || "application/octet-stream",
    size: a.file_size || 0,
    previewUrl: isImage ? url : undefined,
    downloadUrl: url,
  };
}

/**
 * Backend-backed attachment CRUD for a case section/module.
 *
 * `enabled` is false when the working record is still a client-only draft
 * (no backend case yet); callers should then keep their localStorage path.
 */
export function useBackendAttachments(opts: {
  caseId?: string | null;
  section: PdEcrAttachmentSection;
  moduleId?: string;
}) {
  const { caseId, section, moduleId } = opts;
  const enabled = isBackendCaseId(caseId);
  const [items, setItems] = useState<UiAttachment[]>([]);
  const [loading, setLoading] = useState(false);

  const refresh = useCallback(async () => {
    if (!enabled || !caseId) return;
    setLoading(true);
    try {
      const list = await listPdEcrAttachments({ caseId, section, moduleId });
      setItems(list.map(toUi));
    } finally {
      setLoading(false);
    }
  }, [enabled, caseId, section, moduleId]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const upload = useCallback(
    async (files: FileList | File[] | null): Promise<boolean> => {
      const arr = Array.from(files ?? []);
      if (!enabled || !caseId || arr.length === 0) return false;
      for (const file of arr) {
        await uploadPdEcrAttachment({ caseId, file, section, moduleId });
      }
      await refresh();
      return true;
    },
    [enabled, caseId, section, moduleId, refresh],
  );

  const remove = useCallback(
    async (id?: string): Promise<boolean> => {
      if (!enabled || !id) return false;
      await deletePdEcrAttachment(id);
      await refresh();
      return true;
    },
    [enabled, refresh],
  );

  return { enabled, items, loading, upload, remove, refresh };
}
