"""Read-only working guides from the pinned source projects, indexed separately from executable effects."""
from core import ROOT

def guide(key, name, group, relative):
    return dict(id=key, name=name, group=group, kind="guide", source=relative)

GUIDES = [
    guide("ds-repurpose","Turn a recording into shorter edits","Digital Samba","digital-samba/docs/repurposing.md"),
    guide("ds-timing","Scene and audio timing","Digital Samba","digital-samba/docs/timing.md"),
    guide("ds-voice","Voiceover production","Digital Samba","digital-samba/docs/voiceover.md"),
    guide("ds-review","Quality control","Digital Samba","digital-samba/docs/qc.md"),
    guide("shot-energy","Plan a launch film’s energy","Shotcraft","shotcraft/references/sequences/promo-energy-arc.md"),
    guide("shot-beats","Cut to music","Shotcraft","shotcraft/references/music-beat-sync.md"),
    guide("shot-sound","Design the sound edit","Shotcraft","shotcraft/references/sound-design.md"),
    guide("shot-workbench","Use the multitrack workbench","Shotcraft","shotcraft/references/workbench.md"),
    guide("fx-plan","Direct video effects","Video Effects","video-effects/SKILL.md"),
    guide("caption-plan","Direct animated captions","Caption Styles","caption-styles/SKILL.md"),
    guide("vai-beat","Build a beat map","Vaibhav","vaibhav-editor/references/beat-map.md"),
    guide("vai-kinetic","Direct a kinetic promo","Vaibhav","vaibhav-editor/references/styles/kinetic-promo.md"),
    guide("vai-transition","Choose transitions and sound","Vaibhav","vaibhav-editor/references/transitions-sound.md"),
    guide("rm-patterns","Motion design patterns","Remotion Motion Graphics","remotion-skill/remotion-motion-graphics/references/motion-patterns.md"),
    guide("rm-design","Motion design rules","Remotion Motion Graphics","remotion-skill/remotion-motion-graphics/references/design-rules.md"),
    guide("ff-author","Author and render a Rust / SVG production","FFrames","fframes/skills/fframes-video/SKILL.md"),
]
GUIDE_FILES = {row["id"]: ROOT/"upstream"/row["source"] for row in GUIDES}
