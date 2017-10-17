"""/* Copyright(C) 2013, OpenSAR by Fan Wang(parai). All rights reserved.
 *
 * This file is part of OpenSAR.
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program. If not, see <http://www.gnu.org/licenses/>.
 *
 * Email: parai@foxmail.com
 * Source Open At: https://github.com/parai/OpenSAR/
 */
"""
import sys,os
from .GCF import *
from .util import *

__all__ = ['GenOS','gen_askar']

def GenOS(root,dir):
    global __dir
    GLInit(root)
    if(len(GLGet('TaskList')) == 0):return
    os_list = []
    for lst in root:
        for obj in lst:
            os_list.append(obj)
    gen_askar(dir,os_list)
    print('    >>> Gen OS DONE <<<')

def fixupRes(prefix,os_list):
    task_list = ScanFrom(os_list,'Task')
    for res in ScanFrom(os_list,'%sResource'%(prefix)):
        prio = 0;
        for tsk in task_list:
            for res2 in GLGet(tsk, 'ResourceList'):
                if(GAGet(res,'Name') == GAGet(res2,'Name')):
                    GASet(res2,'Type',prefix)
                    if(prio<Integer(GAGet(tsk,'Priority'))):
                       prio=Integer(GAGet(tsk,'Priority'))
        GASet(res,'Priority',str(prio))

def fixupEvt(os_list):
    evList=ScanFrom(os_list,'Event')
    for tsk in ScanFrom(os_list,'Task'):
        masks=[]
        for ev in GLGet(tsk, 'EventList'):
            for ev2 in evList:
                if(GAGet(ev,'Name')==GAGet(ev,'Name')):
                    GASet(ev,'Mask',GAGet(ev2,'Mask'))
                    if(GAGet(ev,'Mask').upper()!='AUTO'):
                        masks.append(Integer(GAGet(ev,'Mask')))
        for ev in GLGet(tsk, 'EventList'):
            if(GAGet(ev,'Mask').upper()=='AUTO'):
                for id in range(0,32):
                    mask = 1<<id
                    try:
                        masks.index(mask)
                    except ValueError:
                        masks.append(mask)
                        GASet(ev,'Mask',hex(mask))
                        break
def fixup(os_list):
    fixupRes('', os_list)
    fixupRes('Internal', os_list)
    fixupEvt(os_list)

def GenH(gendir,os_list):
    fixup(os_list)
    fp = open('%s/Os_Cfg.h'%(gendir),'w')
    fp.write(GHeader('Os',Vendor='askar'))
    fp.write('#ifndef OS_CFG_H_\n#define OS_CFG_H_\n\n')
    fp.write('/* ============================ [ INCLUDES  ] ====================================================== */\n')
    fp.write('#include "kernel.h"\n')
    fp.write('/* ============================ [ MACROS    ] ====================================================== */\n')
    fp.write('#define __ASKAR_OS__\n\n')
    general = ScanFrom(os_list,'General')[0]
    if(GAGet(general,'ErrorHook') != 'NULL'):
        fp.write('#define OS_USE_ERROR_HOOK\n')
    fp.write('#define OS_STATUS %s\n'%(GAGet(general,'Status')))
    fp.write('\n\n')
    task_list = ScanFrom(os_list,'Task')
    maxPrio = 0
    multiPrio = False
    multiAct  = False
    sumAct = 0
    prioList=[]
    prioAct={}
    maxPrioAct=0
    for id,task in enumerate(task_list):
        prio = Integer(GAGet(task,'Priority'))
        act  = Integer(GAGet(task,'Activation'))
        sumAct += act
        try:
            prioAct[prio] += act
        except KeyError:
            prioAct[prio] = act
        if(Integer(GAGet(task,'Activation')) > 1):
            multiAct = True;
        try:
            prioList.index(prio)
            multiPrio = True
        except ValueError:
            prioList.append(prio)
        if(prio > maxPrio):
            maxPrio = prio
    for prio,act in prioAct.items():
        if(maxPrioAct<act):
            maxPrioAct=act
    maxPrioAct+=1 # in case resource ceiling
    seqMask=0
    seqShift=0
    for i in range(1,maxPrioAct+1):
        seqMask|=i
    for i in range(0,32):
        if((seqMask>>i)==0):
            seqShift=i
            break
    fp.write('#define PRIORITY_NUM %s\n'%(maxPrio))
    fp.write('#define ACTIVATION_SUM %s\n'%(sumAct+1))
    if(multiPrio):
        fp.write('#define MULTIPLY_TASK_PER_PRIORITY\n')
        fp.write('#define SEQUENCE_MASK 0x%Xu\n'%(seqMask))
        fp.write('#define SEQUENCE_SHIFT %d\n'%(seqShift))
    if(multiAct):
        fp.write('#define MULTIPLY_TASK_ACTIVATION\n')
    fp.write('\n\n')
    for id,task in enumerate(task_list):
        fp.write('#define TASK_ID_%-32s %-3s /* priority = %s */\n'%(GAGet(task,'Name'),id,GAGet(task,'Priority')))
    fp.write('#define TASK_NUM%-32s %s\n\n'%(' ',id+1))
    fp.write('/* alternative Task ID name */\n')
    for id,task in enumerate(task_list):
        fp.write('#define %-32s %-3s /* priority = %s */\n'%(GAGet(task,'Name'),id,GAGet(task,'Priority')))
    fp.write('\n\n')
    alarm_list = ScanFrom(os_list,'Alarm')
    appmode = []
    for id,obj in enumerate(task_list+alarm_list):
        for mode in GLGet(obj,'ApplicationModeList'):
            if(GAGet(mode,'Name') != 'OSDEFAULTAPPMODE'):
                try:
                    appmode.index(GAGet(mode,'Name'))
                except ValueError:
                    appmode.append(GAGet(mode,'Name'))
    for id,mode in enumerate(appmode):
        fp.write('#define %s ((AppModeType)(1<<%s))\n'%(mode, id+1))

    withEvt = False
    for id,task in enumerate(task_list):
        for mask,ev in enumerate(GLGet(task,'EventList')):
            withEvt = True
            mask = GAGet(ev,'Mask')
            fp.write('#define EVENT_MASK_%-40s %s\n'%('%s_%s'%(GAGet(task,'Name'),GAGet(ev,'Name')),mask))
            fp.write('#define %-51s %s\n'%(GAGet(ev,'Name'),mask))
    fp.write('\n')
    if(withEvt):
        fp.write('\n#define EXTENDED_TASK\n\n')

    res_list = ScanFrom(os_list, 'Resource')
    for id,res in enumerate(res_list):
        if(GAGet(res,'Name') == 'RES_SCHEDULER'):continue
        fp.write('#define RES_ID_%-32s %s\n'%(GAGet(res,'Name'),id+1))
        fp.write('#define %-39s %s\n'%(GAGet(res,'Name'),id+1))
    fp.write('#define RESOURCE_NUM %s\n\n'%(len(res_list)+1))
    id = -1
    counter_list = ScanFrom(os_list,'Counter')
    for id,counter in enumerate(counter_list):
        fp.write('#define COUNTER_ID_%-32s %s\n'%(GAGet(counter,'Name'),id))
        fp.write('#define %-43s %s\n'%(GAGet(counter,'Name'),id))
    fp.write('#define COUNTER_NUM%-32s %s\n\n'%(' ',id+1))
    id = -1
    for id,alarm in enumerate(alarm_list):
        fp.write('#define ALARM_ID_%-32s %s\n'%(GAGet(alarm,'Name'),id))
        fp.write('#define %-41s %s\n'%(GAGet(alarm,'Name'),id))
    fp.write('#define ALARM_NUM%-32s %s\n\n'%(' ',id+1))
    fp.write('\n\n')
    fp.write('/* ============================ [ TYPES     ] ====================================================== */\n')
    fp.write('/* ============================ [ DECLARES  ] ====================================================== */\n')
    fp.write('/* ============================ [ DATAS     ] ====================================================== */\n')
    fp.write('/* ============================ [ LOCALS    ] ====================================================== */\n')
    fp.write('/* ============================ [ FUNCTIONS ] ====================================================== */\n')
    for id,task in enumerate(task_list):
        fp.write('extern TASK(%s);\n'%(GAGet(task,'Name')))
    fp.write('\n\n')
    for id,alarm in enumerate(alarm_list):
        fp.write('extern ALARM(%s);\n'%(GAGet(alarm,'Name')))
    fp.write('\n\n')
    fp.write('#endif /*OS_CFG_H_*/\n\n')
    fp.close()
    
def GenC(gendir,os_list):
    fp = open('%s/Os_Cfg.c'%(gendir),'w')
    fp.write(GHeader('Os',Vendor='askar'))
    fp.write('/* ============================ [ INCLUDES  ] ====================================================== */\n')
    fp.write('#include "kernel_internal.h"\n')
    fp.write('/* ============================ [ MACROS    ] ====================================================== */\n')
    fp.write('/* ============================ [ TYPES     ] ====================================================== */\n')
    fp.write('/* ============================ [ DECLARES  ] ====================================================== */\n')
    fp.write('/* ============================ [ DATAS     ] ====================================================== */\n')
    task_list = ScanFrom(os_list,'Task')
    for id,task in enumerate(task_list):
        fp.write('static uint32_t %s_Stack[(%s*4+sizeof(uint32_t)-1)/sizeof(uint32_t)];\n'%(GAGet(task,'Name'),GAGet(task,'StackSize')))
        if(len(GLGet(task,'EventList')) > 0):
            fp.write('static EventVarType %s_EventVar;\n'%(GAGet(task,'Name')))
    fp.write('#if (OS_STATUS == EXTENDED)\n')
    for id,task in enumerate(task_list):
        cstr = ''
        for res in GLGet(task,'ResourceList'):
            cstr += '\t\tcase RES_ID_%s:\n'%(GAGet(res,'Name'))
        fp.write('''static boolean %s_CheckAccess(ResourceType ResID)
{
    boolean bAccess = FALSE;

    switch(ResID)
    {
        case RES_SCHEDULER:
%s            bAccess = TRUE;
        break;
        default:
            break;
    }

    return bAccess;
}\n'''%(GAGet(task,'Name'),cstr))
    fp.write('#endif\n')
    fp.write('const TaskConstType TaskConstArray[TASK_NUM] =\n{\n')
    for id,task in enumerate(task_list):
        runPrio = GAGet(task,'Priority')
        if(GAGet(task,'Schedule')=='NON'):
            runPrio = 'PRIORITY_NUM'
        else:
            # generall task should has at most one internal resource
            assert(len(GLGet(task,'InternalResource'))<=1)
            for res in GLGet(task,'InternalResource'):
                if(Integer(GLGet(res,'Priority')) > Integer(runPrio)):
                    runPrio = GLGet(res,'Priority')
        maxAct = Integer(GAGet(task,'Activation'))
        event  = 'NULL'
        if(len(GLGet(task,'EventList')) > 0):
            if(maxAct > 1):
                raise Exception('Task<%s>: multiple requesting of task activation allowed for basic tasks'%(GAGet(task,'Name')))
            maxAct = 1
            event = '&%s_EventVar'%(GAGet(task,'Name'))
        fp.write('\t{\n')
        fp.write('\t\t/*.pStack =*/ %s_Stack,\n'%(GAGet(task,'Name')))
        fp.write('\t\t/*.stackSize =*/ sizeof(%s_Stack),\n'%(GAGet(task,'Name')))
        fp.write('\t\t/*.entry =*/ TaskMain%s,\n'%(GAGet(task,'Name')))
        fp.write('\t\t#ifdef EXTENDED_TASK\n')
        fp.write('\t\t/*.pEventVar =*/ %s,\n'%(event))
        fp.write('\t\t#endif\n')
        fp.write('\t\t#if (OS_STATUS == EXTENDED)\n')
        fp.write('\t\t/*.CheckAccess =*/ %s_CheckAccess,\n'%(GAGet(task,'Name')))
        fp.write('\t\t#endif\n')
        fp.write('\t\t/*.initPriority =*/ %s,\n'%(GAGet(task,'Priority')))
        fp.write('\t\t/*.runPriority =*/ %s,\n'%(runPrio))
        fp.write('\t\t/*.name =*/ "%s",\n'%(GAGet(task,'Name')))
        fp.write('\t\t#ifdef MULTIPLY_TASK_ACTIVATION\n')
        fp.write('\t\t/*.maxActivation =*/ %s,\n'%(maxAct))
        fp.write('\t\t#endif\n')
        fp.write('\t\t/*.autoStart =*/ %s,\n'%(GAGet(task,'Autostart').upper()))
        fp.write('\t},\n')
    fp.write('};\n\n')
    fp.write('const ResourceConstType ResourceConstArray[RESOURCE_NUM] =\n{\n')
    fp.write('\t{\n')
    fp.write('\t\t/*.ceilPrio =*/ PRIORITY_NUM, /* RES_SCHEDULER */\n')
    fp.write('\t},\n')
    res_list = ScanFrom(os_list, 'Resource')
    for id,res in enumerate(res_list):
        if(GAGet(res,'Name') == 'RES_SCHEDULER'):continue
        fp.write('\t{\n')
        fp.write('\t\t/*.ceilPrio =*/ %s, /* %s */\n'%(GAGet(res,'Priority'),GAGet(res,'Name')))
        fp.write('\t},\n')
    fp.write('};\n\n')
    counter_list = ScanFrom(os_list,'Counter')
    if(len(counter_list) > 0):
        fp.write('CounterVarType CounterVarArray[COUNTER_NUM];\n')
        fp.write('const CounterConstType CounterConstArray[COUNTER_NUM] =\n{\n')
        for id,counter in enumerate(counter_list):
            fp.write('\t{\n')
            fp.write('\t\t/*.pVar=*/&CounterVarArray[COUNTER_ID_%s],\n'%(GAGet(counter,'Name')))
            fp.write('\t\t/*.base=*/{\n\t\t\t/*.maxallowedvalue=*/%s,\n'%(GAGet(counter,'MaxAllowed')))
            fp.write('\t\t\t/*.ticksperbase=*/%s,\n'%(GAGet(counter,'TicksPerBase')))
            fp.write('\t\t\t/*.mincycle=*/%s\n\t\t}\n'%(GAGet(counter,'MinCycle')))
            fp.write('\t},\n')
        fp.write('};\n\n')
    alarm_list = ScanFrom(os_list,'Alarm')
    if(len(alarm_list) > 0):
        for id,alarm in enumerate(alarm_list):
            fp.write('static void %s_Action(void)\n{\n'%(GAGet(alarm,'Name')))
            if(GAGet(alarm,'Action').upper() == 'ACTIVATETASK'):
                fp.write('\t(void)ActivateTask(TASK_ID_%s);\n'%(GAGet(alarm,'Task')))
            elif(GAGet(alarm,'Action').upper() == 'SETEVENT'):
                fp.write('\t(void)SetEvent(TASK_ID_%s,EVENT_MASK_%s);\n'%(GAGet(alarm,'Task'),GAGet(alarm,'Event')))
            elif(GAGet(alarm,'Action').upper() == 'CALLBACK'):
                fp.write('\textern ALARM(%s);\n\tAlarmMain%s();\n'%(GAGet(alarm,'Callback'),GAGet(alarm,'Callback')))
            else:
                assert(0)
            fp.write('}\n')
            fp.write('static void %s_Autostart(void)\n{\n'%(GAGet(alarm,'Name')))
            if(GAGet(alarm,'Autostart').upper() == 'TRUE'):
                fp.write('\t(void)SetAbsAlarm(%s, %s);\n'%(GAGet(alarm,'StartTime'),GAGet(alarm,'Period')))
            else:
                fp.write('\t/* not autostart */\n')
            fp.write('}\n')
        fp.write('AlarmVarType AlarmVarArray[ALARM_NUM];\n')
        fp.write('const AlarmConstType AlarmConstArray[ALARM_NUM] =\n{\n')
        for id,alarm in enumerate(alarm_list):
            fp.write('\t{\n')
            fp.write('\t\t/*.pVar=*/&AlarmVarArray[ALARM_ID_%s],\n'%(GAGet(alarm,'Name')))
            fp.write('\t\t/*.pCounter=*/&CounterConstArray[COUNTER_ID_%s],\n'%(GAGet(alarm,'Counter')))
            fp.write('\t\t/*.Start=*/%s_Autostart,\n'%(GAGet(alarm,'Name')))
            fp.write('\t\t/*.Action=*/%s_Action,\n'%(GAGet(alarm,'Name')))
            fp.write('\t},\n')
        fp.write('};\n\n')
    fp.write('/* ============================ [ LOCALS    ] ====================================================== */\n')
    fp.write('/* ============================ [ FUNCTIONS ] ====================================================== */\n')
    
    fp.close()

def gen_askar(gendir,os_list):
    GenH(gendir,os_list)
    GenC(gendir,os_list)