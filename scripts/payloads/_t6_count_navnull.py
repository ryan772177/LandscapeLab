import json, unreal
_o={"ok":False}
try:
    _eas=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    n=0; sample=None
    for a in _eas.get_all_level_actors():
        try: l=a.get_actor_label()
        except Exception: continue
        if l.startswith("NavNull_"):
            n+=1
            if sample is None:
                ac=a.get_editor_property("area_class")
                o2,e2=a.get_actor_bounds(False)
                sample={"label":l,"area_class":str(ac),"ext":[round(e2.x,1),round(e2.y,1),round(e2.z,1)],"topz":round(o2.z+e2.z,1)}
    _o["navnull_count"]=n; _o["sample"]=sample; _o["ok"]=True
except Exception as e:
    _o["error"]="%s: %s"%(type(e).__name__,e)
print("__T6_COUNT__"+json.dumps(_o))
