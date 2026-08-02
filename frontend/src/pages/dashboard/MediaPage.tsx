import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";

import { getMediaAnalytics } from "../../api/analytics";
import { PageHeader } from "../../components/layout/PageHeader";
import { MediaTable } from "../../components/MediaTable";
import { QueryState } from "../../components/QueryState";
import { EmptyState, Panel, SegmentedControl } from "../../components/ui";

const TYPE_OPTIONS = [
  { value: "", label: "All" },
  { value: "IMAGE", label: "Images" },
  { value: "VIDEO", label: "Videos" },
  { value: "CAROUSEL_ALBUM", label: "Carousels" },
] as const;

export function MediaPage() {
  const [mediaType, setMediaType] = useState<
    "" | "IMAGE" | "VIDEO" | "CAROUSEL_ALBUM"
  >("");

  const media = useQuery({
    queryKey: ["media-analytics", mediaType],
    queryFn: () => getMediaAnalytics(100, mediaType || undefined),
  });

  const items = media.data ?? [];

  return (
    <>
      <PageHeader
        eyebrow="Analytics"
        title="Posts"
        description="Every post Instalysis has synced, with its stored metrics."
        actions={
          <SegmentedControl
            label="Post type"
            options={TYPE_OPTIONS}
            value={mediaType}
            onChange={setMediaType}
          />
        }
      />

      <QueryState
        isLoading={media.isLoading}
        error={media.error}
        loadingLabel="Loading posts"
      >
        {items.length === 0 ? (
          <EmptyState
            title={mediaType ? "No posts of this type" : "No posts synced yet"}
            body={
              mediaType ? (
                "Try a different post type."
              ) : (
                <>
                  Run “Sync from Instagram” in <Link to="/settings">Settings</Link>{" "}
                  to pull your posts in.
                </>
              )
            }
          />
        ) : (
          <div className="stack">
            <p className="muted text-sm">
              {items.length} post{items.length === 1 ? "" : "s"}
            </p>
            <Panel>
              <MediaTable items={items} />
            </Panel>
          </div>
        )}
      </QueryState>
    </>
  );
}
