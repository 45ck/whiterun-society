using Mutagen.Bethesda;
using Mutagen.Bethesda.Plugins;
using Mutagen.Bethesda.Skyrim;

// An additive plugin: no vanilla records, original route records or save marker
// records are replaced. The controller never needs a JavaScript Alias handle.
static class RouterBuilder {
 public static void Build(string output) {
  var rest=Path.GetFileName(output)=="WhiterunRest.esp";
  var pooled=Path.GetFileName(output)=="WhiterunLanes.esp";
  var count=pooled?8:1;
  var prefix=rest?"WSSocietyRest":"WSSocietyRouter";
  var key=ModKey.FromNameAndExtension(Path.GetFileName(output));
  var mod=new SkyrimMod(key,SkyrimRelease.SkyrimSE);
  for(var slot=0;slot<count;slot++){
  uint first=(uint)(0x800+slot*0x10);var suffix=pooled?slot.ToString():"";
  var quest=new Quest(new FormKey(key,first),SkyrimRelease.SkyrimSE){
   EditorID=prefix+"Quest"+suffix,Name=rest?"Whiterun Society seated rest":"Whiterun Society resident travel",Priority=95,Flags=0,NextAliasID=2,
   VirtualMachineAdapter=new QuestAdapter{Version=5,ObjectFormat=2}};
  var travel=new Package(new FormKey(key,first+1),SkyrimRelease.SkyrimSE){
   EditorID=(rest?prefix+"Package":"WSSocietyRouterTravel")+suffix,Type=Package.Types.Package,
   Flags=Package.Flag.PreferredSpeed,PreferredSpeed=Package.Speed.Walk,
   ScheduleMonth=-1,ScheduleDayOfWeek=Package.DayOfWeek.Any,ScheduleDate=0,
   ScheduleHour=-1,ScheduleMinute=-1,ScheduleDurationInMinutes=0,
   DataInputVersion=3,XnamMarker=new byte[]{5},Unknown3=new byte[]{0,0,0}};
  travel.OwnerQuest.SetTo(quest.FormKey);
  if(rest){
   // SitTarget and its data slots were inspected in the user's owned Skyrim.esm.
   travel.PackageTemplate.SetTo(new FormKey(ModKey.FromNameAndExtension("Skyrim.esm"),0xA9277));
   travel.DataInputVersion=2;travel.XnamMarker=new byte[]{17};
   travel.Data[16]=new PackageDataTarget{Type=PackageDataTarget.Types.SingleRef,Target=new PackageTargetAlias{Alias=1,CountOrDistance=0}};
   travel.Data[3]=new PackageDataFloat{Data=0};travel.Data[4]=new PackageDataBool{Data=false};
  }else{
   travel.PackageTemplate.SetTo(new FormKey(ModKey.FromNameAndExtension("Skyrim.esm"),0x16FAA));
   travel.Data[0]=new PackageDataLocation{Location=new LocationTargetRadius{
    Target=new LocationFallback{Type=LocationTargetRadius.LocationType.AliasForReference,Data=1},Radius=150}};
   travel.Data[2]=new PackageDataBool{Data=false};travel.Data[4]=new PackageDataBool{Data=false};
  }
  var actor=new QuestAlias{ID=0,Name="ManagedResident",Type=QuestAlias.TypeEnum.Reference,
   Flags=QuestAlias.Flag.Optional|QuestAlias.Flag.AllowReserved};
  actor.PackageData.Add(travel.FormKey);quest.Aliases.Add(actor);
  quest.Aliases.Add(new QuestAlias{ID=1,Name="AgentDestination",Type=QuestAlias.TypeEnum.Reference,
   Flags=QuestAlias.Flag.Optional|QuestAlias.Flag.AllowReserved|QuestAlias.Flag.AllowReuseInQuest});
  var script=new ScriptEntry{Name="WSSocietyRouter"};
  string[] properties={"ResidentReference","DestinationReference","RequestSerial","AcknowledgedSerial","RouteStatus"};
  for(var i=0;i<properties.Length;i++){
   var form=new FormKey(key,(uint)(first+2+i));
   if(i<2)mod.FormLists.Add(new FormList(form,SkyrimRelease.SkyrimSE){EditorID=(rest?"WSRest":"WSRouter")+properties[i]+suffix});
   else mod.Globals.Add(new GlobalFloat(form,SkyrimRelease.SkyrimSE){EditorID=(rest?"WSRest":"WSRouter")+properties[i]+suffix,Data=0});
   var property=new ScriptObjectProperty{Name=properties[i],Alias=-1,Flags=ScriptProperty.Flag.Edited};
   property.Object.SetTo(form);script.Properties.Add(property);
  }
  quest.VirtualMachineAdapter.Scripts.Add(script);
  mod.Quests.Add(quest);mod.Packages.Add(travel);
  }
  Directory.CreateDirectory(Path.GetDirectoryName(output)!);mod.WriteToBinary(output);
  using var check=SkyrimMod.CreateFromBinaryOverlay(output,SkyrimRelease.SkyrimSE);
  foreach(var q in check.Quests){
  var s=q.VirtualMachineAdapter!.Scripts.Single();
  if(check.Quests.Count!=count||check.Packages.Count!=count||check.FormLists.Count!=2*count||check.Globals.Count!=3*count||q.Aliases.Count!=2||
     q.Aliases.Any(a=>a.Flags?.HasFlag(QuestAlias.Flag.Optional)!=true||!a.ForcedReference.IsNull)||
     s.Name!="WSSocietyRouter"||s.Properties.Count!=5||
     s.Properties.OfType<IScriptObjectPropertyGetter>().Any(p=>p.Alias!=-1||p.Object.FormKey.ModKey!=key))
   throw new InvalidDataException("Router plugin readback failed");
  if(q.Aliases[0].PackageData.Single().FormKey.ID!=q.FormKey.ID+1 ||
     s.Properties.OfType<IScriptObjectPropertyGetter>().Select(p=>p.Object.FormKey.ID).OrderBy(id=>id)
       .SequenceEqual(Enumerable.Range(2,5).Select(offset=>q.FormKey.ID+(uint)offset))!=true)
   throw new InvalidDataException("Routing slot references another slot's records");
  }
  if(rest && (check.Packages.Single().PackageTemplate.FormKey.ID!=0xA9277 || check.Packages.Single().Data[16] is not IPackageDataTargetGetter target || target.Target is not IPackageTargetAliasGetter alias || alias.Alias!=1))throw new InvalidDataException("Rest target readback failed");
  Console.WriteLine($"Built original Papyrus mailbox {(rest?"rest":"travel")} router: {output}");
 }
}
