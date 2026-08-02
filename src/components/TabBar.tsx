import { useTabs } from "../state/TabsContext";
import { useTabClose } from "../hooks/useTabClose";
import { basenameForDisplay } from "../lib/displayPath";

export function TabBar() {
  const { tabs, activeTabPath, setActiveTab } = useTabs();
  const { closeTab } = useTabClose();

  if (tabs.length === 0) {
    return null;
  }

  return (
    <div className="tab-bar" role="tablist">
      {tabs.map((tab) => {
        const label = basenameForDisplay(tab.path);
        const isActive = tab.path === activeTabPath;
        return (
          <div
            key={tab.path}
            role="tab"
            aria-selected={isActive}
            className={"tab-bar__tab" + (isActive ? " tab-bar__tab--active" : "")}
            title={tab.path}
            onClick={() => setActiveTab(tab.path)}
          >
            <span className="tab-bar__label">{label}</span>
            <button
              type="button"
              className="tab-bar__close"
              aria-label={`${label} を閉じる`}
              title="閉じる"
              onClick={(event) => {
                event.stopPropagation();
                closeTab(tab.path);
              }}
            >
              ×
            </button>
          </div>
        );
      })}
    </div>
  );
}
