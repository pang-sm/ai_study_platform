import { LegalDocument, LegalList, LegalSection } from './components/legal-document';

/**
 * 隐私政策 V1.
 *
 * This document is an inventory of what the running product actually does, checked against the
 * code rather than written from a template: the cookie list is the two cookies `backend/main.py`
 * issues, the AI clause describes the request record that `backend/usage/models.py` stores, and
 * the "no third parties besides these" clause is true because the frontend loads no analytics,
 * ad or social script. Where a reader would expect a claim we cannot support — end-to-end
 * encryption, a support mailbox, self-service deletion — the clause says what is missing.
 */
export function PrivacyPage() {
  return (
    <LegalDocument
      title="隐私政策"
      version="版本 V1"
      updatedAt="2026-09-21"
      summary="本政策说明「智学AI」项目运营者在提供智学平台时，会收集哪些信息、如何使用与保存它们，以及你可以如何查阅、更正与删除这些信息。"
    >
      <LegalSection n={1} title="适用范围">
        <p>
          本政策适用于智学平台及其后续提供的网页、客户端（以下称“本服务”），包括统一账号下的三个学习空间（专业学习、考研学习、编程学习）与复习、学习报告、会员、用量等共享功能。
        </p>
        <p>
          本政策与《用户协议》共同构成你使用本服务的约定；两者就个人信息处理的表述不一致时，以本政策为准。
        </p>
      </LegalSection>

      <LegalSection n={2} title="注册与登录时收集的信息">
        <p>
          注册需要先验证邮箱。我们会向你填写的邮箱发送一封验证码邮件：验证码为 6 位数字，10 分钟内有效，最多可尝试 5 次；服务器只保存验证码的哈希值，不保存验证码原文。验证通过后才能创建账号。
        </p>
        <p>创建账号时会提交并保存以下信息：</p>
        <LegalList
          items={[
            '账号名：用于登录与在学习记录中标识你。',
            '密码：不会以明文保存，服务器只保存 bcrypt 哈希值，我们也无法还原你的明文密码。',
            '邮箱地址：用于邮箱验证码登录，以及账号相关的必要验证邮件。',
          ]}
        />
        <p>
          登录后，你可以在“我的学习档案 → 账号与安全”中选择绑定邮箱或手机号；手机号绑定通过短信验证码完成。绑定后的邮箱与手机号当前不支持自行更换。
        </p>
        <p>
          登录成功后，服务器会签发一个登录会话 Cookie，并在服务端保存会话记录（签发时间、最近活动时间、到期时间；令牌以哈希值保存）。会话有效期为 30 天。
        </p>
        <p>个人资料中可自行填写昵称、年级、专业、学期，用于在各学习空间与学习报告中展示。</p>
      </LegalSection>

      <LegalSection n={3} title="学习过程中产生的数据">
        <p>你使用学习功能时，会在服务端产生并保存以下数据：</p>
        <LegalList
          items={[
            '学习设置：你声明的课程、选择的备考方向与科目、选择的编程语言。',
            '学习内容：你上传的资料文件及其解析结果、知识点、系统为你生成的练习题、你做错的题目与对应的错题分析。',
            '学习行为：练习作答与判分结果、复习安排与完成情况、学习计划与任务、代码运行与测试结果、学习报告，以及为形成这些记录而保存的学习事件（例如“打开资料”“完成一次练习作答”“提交代码”）。',
            '学习状态：学习空间中展示的学习状态，由上述已有记录按确定性规则计算得出，不额外采集数据。',
          ]}
        />
      </LegalSection>

      <LegalSection n={4} title="AI 功能涉及的数据处理">
        <p>只有你主动使用 AI 功能时，才会发起 AI 请求。</p>
        <LegalList
          items={[
            '为完成一次请求，我们会把该次任务所需的上下文发送给模型服务：你的提问或指令、当前题目或代码、相关资料的文本片段，以及必要的学习上下文（例如所属学习空间、课程或科目标识）。范围以完成该次任务所必需为限。',
            '请求由我们的服务器发起，你的浏览器不会直接连接模型服务商；模型服务商不会因此直接获得你的账号、密码、邮箱或会话令牌。',
            '每次 AI 请求会在服务端留下一条记录：请求标识、账号、请求的能力类型、所属学习空间与上下文标识、请求状态、该次请求的用量计量、耗时与错误类别。这些记录用于额度计量、限流、成本核算与故障排查。',
            'AI 回答下方的反馈（有帮助 / 需要改进及原因）会与该次请求关联保存，用于质量改进。',
          ]}
        />
      </LegalSection>

      <LegalSection n={5} title="使用目的">
        <LegalList
          items={[
            '提供与维护学习功能：解析你上传的资料、生成练习、记录作答与错题、安排复习、生成学习报告。',
            '按你的账号计算与展示学习记录、统计与学习状态。',
            '计量用量与成本，执行会员等级与额度规则。',
            '保障账号与数据安全，防止滥用，排查故障。',
            '依据你的反馈改进功能。',
            '遵守法律法规的要求。',
          ]}
        />
        <p>我们不会将你的学习数据用于向你投放广告，也不会出售你的个人信息。</p>
      </LegalSection>

      <LegalSection n={6} title="数据存储与安全">
        <LegalList
          items={[
            '你的数据保存在本服务自己的服务器上，数据库为服务端数据库。',
            '生产环境通过 HTTPS 提供访问；登录会话 Cookie 具备 HttpOnly 与 SameSite=Lax 属性。',
            '密码使用 bcrypt 哈希保存；邮箱与短信验证码只保存哈希值，并设有有效期与尝试次数上限。',
            '接口按账号隔离数据，身份一律以服务器签发的会话为准，而不是以请求中传入的用户名为准。',
          ]}
        />
        <p>
          除上述措施外，我们没有额外的加密存储层，也不宣称采用了端到端加密。请不要把与学习无关的敏感信息（例如身份证号、银行卡号）上传到本服务。
        </p>
      </LegalSection>

      <LegalSection n={7} title="Cookie 与本地存储">
        <p>本服务使用两个 Cookie，均为提供功能所必需：</p>
        <LegalList
          items={[
            'ai_session：登录会话 Cookie。登录成功后签发，有效期 30 天，带 HttpOnly 与 SameSite=Lax 属性；退出登录后失效。',
            'zhixue_register_email_proof：注册流程中的邮箱验证凭证，只用于注册，10 分钟内有效。',
          ]}
        />
        <p>
          本服务当前不使用 localStorage 或 sessionStorage 保存登录状态或学习数据；退出登录会清除本机缓存的账号学习数据。
        </p>
        <p>本服务不加载第三方统计、广告或社交脚本。</p>
      </LegalSection>

      <LegalSection n={8} title="第三方服务说明">
        <p>为提供功能，下列第三方服务会接触到完成该功能所必需的信息：</p>
        <LegalList
          items={[
            '邮件服务（SMTP）：发送邮箱验证码，会接触收件邮箱地址与验证码内容。',
            '短信服务（部署配置时）：发送手机验证码，会接触手机号与验证码内容。',
            'AI 模型服务商：处理你的 AI 请求，会接触第 4 节所述的请求上下文，并返回结果。',
          ]}
        />
        <p>除上述完成功能所必需的信息外，我们不会主动向第三方提供你的账号与学习数据。</p>
      </LegalSection>

      <LegalSection n={9} title="你的查阅、更正与删除">
        <LegalList
          items={[
            '查阅：在“我的学习档案”中可以查看账号信息、昵称、年级、专业、学期与邮箱 / 手机号绑定状态；在各学习空间中可以查看你的课程或科目设置、资料、练习、错题、计划与学习记录；学习报告与用量记录中可以查看统计与额度消耗。',
            '更正：昵称、年级、专业、学期可在“我的学习档案”中修改；密码可在“账号与安全”中修改；邮箱与手机号绑定后当前不支持自行更换。',
            '删除：当前版本没有提供自助删除账号或批量删除学习数据的功能，也没有数据导出功能。需要删除时，待正式运营渠道建立后可通过该渠道提出（见第 12 节）。',
          ]}
        />
      </LegalSection>

      <LegalSection n={10} title="未成年人保护">
        <p>
          本服务面向一般学习者，没有独立的未成年人账号体系，注册也不要求提交年龄信息。
        </p>
        <p>
          若你未满 18 周岁，请在监护人的同意和指导下使用本服务，并由监护人协助管理账号、密码与用量。
        </p>
      </LegalSection>

      <LegalSection n={11} title="政策更新">
        <p>
          本政策会随功能与法律要求的变化更新。更新后的版本在本页发布，并标注版本与更新日期；如果更新涉及你的重要权利，我们会在产品内以显著方式提示。
        </p>
      </LegalSection>

      <LegalSection n={12} title="联系方式">
        <p>
          本服务目前以项目方式运营，尚未注册公司主体，也没有对外的公司地址、客服电话与客服邮箱。在正式运营主体与对外联络渠道确定之前，本节只列出当前真实存在的方式：
        </p>
        <LegalList
          items={[
            'AI 功能中每次回答下方的反馈入口：可报告该次回答的问题，反馈会与该次请求一起记录。',
          ]}
        />
        <p>
          涉及数据查阅、更正与删除等需要人工处理的事项，本版本尚无受理渠道；相关渠道建立后，我们会在此更新，并在《用户协议》中同步说明。
        </p>
      </LegalSection>
    </LegalDocument>
  );
}
